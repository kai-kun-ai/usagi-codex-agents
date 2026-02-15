"""Mailbox-driven async chain (boss -> manager -> lead -> worker).

This is a first implementation to enforce command hierarchy:
- Boss creates plan and sends it to manager inbox.
- Manager creates assignment/request and sends to lead inbox.
- Lead sends impl request to worker inbox.
- Worker implements in worktree and sends result back.

All handoffs are Markdown files via mailbox.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

from usagi.agents import AgentMessage, CodexCLIBackend, OfflineBackend, UsagiAgent
from usagi.artifacts import write_artifact
from usagi.git_ops import team_branch
from usagi.mailbox import archive_message, deliver_markdown, list_inbox
from usagi.mailbox_parse import parse_mail_markdown
from usagi.org import Organization
from usagi.prompt_compact import compact_for_prompt
from usagi.runtime import RuntimeMode
from usagi.spec import UsagiSpec
from usagi.state import AgentStatus, load_status, save_status

log = logging.getLogger(__name__)


def _event(root: Path, msg: str) -> None:
    try:
        p = root / ".usagi" / "events.log"
        p.parent.mkdir(parents=True, exist_ok=True)
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        with p.open("a", encoding="utf-8") as f:
            f.write(f"[{ts}] {msg}\n")
    except Exception:
        return


def _set(root: Path, status_path: Path | None, agent_id: str, name: str, state: str, task: str) -> None:
    if status_path is not None:
        st = load_status(status_path)
        st.set(AgentStatus(agent_id=agent_id, name=name, state=state, task=task))
        save_status(status_path, st)
    # also log agent activity to events
    _event(root, f"agent: {agent_id} state={state} task={task}")


def boss_handle_spec(
    *,
    root: Path,
    outputs_dir: Path,
    status_path: Path | None,
    org: Organization,
    runtime: RuntimeMode,
    spec: UsagiSpec,
    model: str,
    offline: bool,
    workdir: Path,
    input_rel: str,
    job_id: str,
) -> None:
    """Boss creates plan and delegates to manager inbox."""

    backend = OfflineBackend() if offline else CodexCLIBackend()

    assignment_manager = org.find("dev_mgr") or org.find(runtime.boss_id)
    boss = org.find(runtime.boss_id)
    if boss is None or assignment_manager is None:
        raise RuntimeError("boss/manager not found")

    _set(root, status_path, boss.id, boss.name or boss.id, "working", f"plan: {spec.project}")
    boss_agent = UsagiAgent(
        name=boss.name or boss.id,
        role="planner",
        system_prompt=(
            "あなたは社長(boss)です。絶対に実装しません。\n"
            "依頼を部長に委任できるように、方針/手順/リスク/完了条件をMarkdownで書いてください。\n"
            "必ず `## 決定事項` を含め、箇条書きで書いてください。"
        ),
    )
    plan_prompt = f"目的:\n{spec.objective}\n\nやること:\n" + "\n".join([f"- {t}" for t in spec.tasks])
    plan_msg = boss_agent.run(user_prompt=plan_prompt, model=model, backend=backend)
    write_artifact(workdir, "10-boss-plan.md", plan_msg.content)

    deliver_markdown(
        root=root,
        from_agent=boss.id,
        to_agent=assignment_manager.id,
        title=f"委任: {spec.project or 'default'}",
        kind="boss_plan",
        body=compact_for_prompt(plan_msg.content, stage="boss_plan_to_manager", max_chars=runtime.compress.max_chars_default, enabled=runtime.compress.enabled),
    )

    _set(root, status_path, boss.id, boss.name or boss.id, "idle", "")


def manager_tick(*, root: Path, outputs_dir: Path, status_path: Path | None, org: Organization, runtime: RuntimeMode, model: str, offline: bool) -> None:
    mgr = org.find("dev_mgr")
    if mgr is None:
        return
    for p in list_inbox(root=root, agent_id=mgr.id):
        msg = parse_mail_markdown(p.read_text(encoding="utf-8"))
        if msg.kind != "boss_plan":
            archive_message(root=root, agent_id=mgr.id, message_path=p)
            continue

        _set(root, status_path, mgr.id, mgr.name or mgr.id, "working", "delegate")

        lead = org.find("dev_impl_lead")
        if lead is None:
            archive_message(root=root, agent_id=mgr.id, message_path=p)
            _set(root, status_path, mgr.id, mgr.name or mgr.id, "idle", "")
            return

        deliver_markdown(
            root=root,
            from_agent=mgr.id,
            to_agent=lead.id,
            kind="impl_request",
            title=f"実装依頼: {msg.title}",
            body=msg.body,
        )

        # report upward
        deliver_markdown(
            root=root,
            from_agent=mgr.id,
            to_agent=runtime.boss_id,
            kind="manager_report",
            title=f"部長報告: {msg.title}",
            body=msg.body,
        )

        archive_message(root=root, agent_id=mgr.id, message_path=p)
        _set(root, status_path, mgr.id, mgr.name or mgr.id, "idle", "")


def lead_tick(*, root: Path, status_path: Path | None, org: Organization, runtime: RuntimeMode) -> None:
    lead = org.find("dev_impl_lead")
    if lead is None:
        return
    for p in list_inbox(root=root, agent_id=lead.id):
        msg = parse_mail_markdown(p.read_text(encoding="utf-8"))
        if msg.kind != "impl_request":
            archive_message(root=root, agent_id=lead.id, message_path=p)
            continue

        _set(root, status_path, lead.id, lead.name or lead.id, "working", "assign worker")
        worker = org.find("dev_w1") or org.find("dev_w2")
        if worker is None:
            archive_message(root=root, agent_id=lead.id, message_path=p)
            _set(root, status_path, lead.id, lead.name or lead.id, "idle", "")
            return

        deliver_markdown(
            root=root,
            from_agent=lead.id,
            to_agent=worker.id,
            kind="worker_request",
            title=msg.title,
            body=msg.body,
        )

        archive_message(root=root, agent_id=lead.id, message_path=p)
        _set(root, status_path, lead.id, lead.name or lead.id, "idle", "")


def worker_tick(*, root: Path, status_path: Path | None, org: Organization, runtime: RuntimeMode, model: str, offline: bool, repo_root: Path) -> None:
    worker = org.find("dev_w1")
    lead = org.find("dev_impl_lead")
    if worker is None or lead is None:
        return

    from usagi.approval_pipeline import _run_worker_step_worktree

    backend = OfflineBackend() if offline else CodexCLIBackend()

    for p in list_inbox(root=root, agent_id=worker.id):
        msg = parse_mail_markdown(p.read_text(encoding="utf-8"))
        if msg.kind != "worker_request":
            archive_message(root=root, agent_id=worker.id, message_path=p)
            continue

        _set(root, status_path, worker.id, worker.name or worker.id, "working", "implement")

        # Minimal fake spec
        spec = UsagiSpec(project="usagi-project", objective=msg.title, tasks=[], constraints=[], context="")
        workdir = repo_root / "jobs" / "worker" / p.stem
        workdir.mkdir(parents=True, exist_ok=True)

        impl = _run_worker_step_worktree(
            worker=worker,
            lead=lead,
            plan=AgentMessage(agent_name="boss", role="planner", content=msg.body),
            spec=spec,
            workdir=workdir,
            repo_root=repo_root,
            model=model,
            backend=backend,
            runtime=runtime,
            offline=offline,
        )

        deliver_markdown(
            root=root,
            from_agent=worker.id,
            to_agent=lead.id,
            kind="impl_result",
            title=f"実装結果: {msg.title}",
            body=impl.content,
        )

        archive_message(root=root, agent_id=worker.id, message_path=p)
        _set(root, status_path, worker.id, worker.name or worker.id, "idle", "")
