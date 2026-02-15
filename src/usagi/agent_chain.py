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
from usagi.agent_memory import append_memory, read_memory
from usagi.artifacts import write_artifact
from usagi.git_ops import GitRepo, team_branch
from usagi.report_state import update_boss_report
from usagi.mailbox_parse import MailMessage
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


def manager_tick(*, root: Path, outputs_dir: Path, status_path: Path | None, org: Organization, runtime: RuntimeMode, model: str, offline: bool, repo_root: Path) -> None:
    """Manager inbox handler.

    Handles:
    - boss_plan -> impl_request (to lead) + manager_report (to boss)
    - review_result -> merge_decision/report (+ merge to main if MERGE_OK)
    """

    mgr = org.find("dev_mgr")
    if mgr is None:
        return

    backend = OfflineBackend() if offline else CodexCLIBackend()

    for p in list_inbox(root=root, agent_id=mgr.id):
        msg = parse_mail_markdown(p.read_text(encoding="utf-8"))

        if msg.kind == "boss_plan":
            _set(root, status_path, mgr.id, mgr.name or mgr.id, "working", "delegate")

            lead = org.find("dev_impl_lead")
            if lead is None:
                archive_message(root=root, agent_id=mgr.id, message_path=p)
                _set(root, status_path, mgr.id, mgr.name or mgr.id, "idle", "")
                continue

            # digest using manager memory
            _set(root, status_path, mgr.id, mgr.name or mgr.id, "working", "digest")
            mem = read_memory(root, mgr.id, max_chars=1800)
            digest_agent = UsagiAgent(
                name=mgr.name or mgr.id,
                role="planner",
                system_prompt=(
                    "あなたは開発部長です。社長からの委任を咀嚼し、課長へ具体的に指示してください。\n"
                    "出力は必ず短く。形式:\n"
                    "## 目的\n...\n\n## 指示\n- ...\n\n## 注意\n- ...\n"
                ),
            )
            digest_prompt = (
                "## 社長からの委任\n" + msg.body + "\n\n"
                "## あなたのメモリ（過去の判断/方針）\n" + (mem or "(なし)") + "\n"
            )
            digest_msg = digest_agent.run(user_prompt=digest_prompt, model=model, backend=backend)
            append_memory(root, mgr.id, f"digest: {msg.title}", digest_msg.content)

            _set(root, status_path, mgr.id, mgr.name or mgr.id, "working", "brief")
            deliver_markdown(
                root=root,
                from_agent=mgr.id,
                to_agent=lead.id,
                kind="impl_request",
                title=f"部長指示: {msg.title}",
                body=digest_msg.content,
            )

            # report upward + cross-department share
            deliver_markdown(
                root=root,
                from_agent=mgr.id,
                to_agent=runtime.boss_id,
                kind="manager_report",
                title=f"部長報告: {msg.title}",
                body=digest_msg.content,
            )
            for peer in ["qa_mgr", "ops_mgr"]:
                if org.find(peer) is not None:
                    deliver_markdown(
                        root=root,
                        from_agent=mgr.id,
                        to_agent=peer,
                        kind="assist_request",
                        title=f"協力依頼: {msg.title}",
                        body=(
                            "あなたは同一階層の部長です。以下の依頼/方針を見て、\n"
                            "リスク/懸念/見落とし/追加で確認すべき点を短く返してください。\n\n"
                            + digest_msg.content
                        ),
                    )

            archive_message(root=root, agent_id=mgr.id, message_path=p)
            _set(root, status_path, mgr.id, mgr.name or mgr.id, "idle", "")
            continue

        if msg.kind == "review_result":
            _set(root, status_path, mgr.id, mgr.name or mgr.id, "working", "merge decision")

            agent = UsagiAgent(
                name=mgr.name or mgr.id,
                role="planner",
                system_prompt=(
                    "あなたは部長(manager)です。\n"
                    "課長のレビュー結果を踏まえ、課ブランチを main にマージしてよいか判断してください。\n"
                    "判断は 'MERGE_OK' / 'NEED_MORE_REVIEW' / 'ESCALATE_TO_BOSS' のいずれかを必ず含めてください。"
                ),
            )
            decision_msg = agent.run(user_prompt=msg.body, model=model, backend=backend)
            decision_text = decision_msg.content.upper()

            # apply merge if OK and lead approved
            approved = "APPROVE" in msg.body.upper()
            if approved and "MERGE_OK" in decision_text:
                try:
                    repo = GitRepo(repo_root / ".usagi" / "repo")
                    repo.ensure_repo()
                    repo.ensure_initial_commit()
                    team = team_branch("dev_impl_lead")
                    wt_dir = repo_root / ".usagi" / "worktrees" / team
                    repo.merge_to_main_and_delete_branch(team)
                    repo.worktree_remove(wt_dir)
                except Exception as e:  # noqa: BLE001
                    _event(root, f"merge failed: {type(e).__name__}: {e}")

            body = (
                "## 部長判断\n" + decision_msg.content.strip() + "\n\n" +
                "(元のレビュー結果)\n" + compact_for_prompt(msg.body, stage="manager_review", max_chars=runtime.compress.max_chars_default, enabled=runtime.compress.enabled)
            )

            deliver_markdown(
                root=root,
                from_agent=mgr.id,
                to_agent=runtime.boss_id,
                kind="manager_report",
                title=f"部長報告(レビュー結果): {msg.title}",
                body=body,
            )

            # update boss report directly as well (so boss can pick next)
            try:
                spec = UsagiSpec(project="usagi-project", objective=msg.title, tasks=[], constraints=[], context="")
                update_boss_report(
                    outputs_dir=outputs_dir,
                    spec=spec,
                    job_id=p.stem,
                    workdir=repo_root,
                    input_rel=msg.title,
                    messages=[decision_msg],
                    note="部長: レビュー結果を受けて判断しました。",
                    boss_summary=decision_msg.content.splitlines()[0] if decision_msg.content else "",
                    boss_decisions=[line.strip("- ") for line in decision_msg.content.splitlines() if line.strip().startswith("-")],
                )
            except Exception:
                pass

            archive_message(root=root, agent_id=mgr.id, message_path=p)
            _set(root, status_path, mgr.id, mgr.name or mgr.id, "idle", "")
            continue

        # unknown kind
        archive_message(root=root, agent_id=mgr.id, message_path=p)


def lead_tick(*, root: Path, status_path: Path | None, org: Organization, runtime: RuntimeMode, model: str, offline: bool) -> None:
    lead = org.find("dev_impl_lead")
    mgr = org.find("dev_mgr")
    if lead is None:
        return

    backend = OfflineBackend() if offline else CodexCLIBackend()

    for p in list_inbox(root=root, agent_id=lead.id):
        msg = parse_mail_markdown(p.read_text(encoding="utf-8"))

        if msg.kind == "impl_request":
            _set(root, status_path, lead.id, lead.name or lead.id, "working", "digest")
            worker = org.find("dev_w1") or org.find("dev_w2")
            if worker is None:
                archive_message(root=root, agent_id=lead.id, message_path=p)
                _set(root, status_path, lead.id, lead.name or lead.id, "idle", "")
                continue

            mem = read_memory(root, lead.id, max_chars=1800)
            digest_agent = UsagiAgent(
                name=lead.name or lead.id,
                role="planner",
                system_prompt=(
                    "あなたは開発実装課長です。部長指示を咀嚼し、ワーカーへ実装指示を作ってください。\n"
                    "出力は短く、実装に必要な情報だけ。形式:\n"
                    "## 実装指示\n- ...\n\n## 受け入れ条件\n- ...\n\n## 注意\n- ...\n"
                ),
            )
            digest_prompt = (
                "## 部長指示\n" + msg.body + "\n\n"
                "## あなたのメモリ（過去の判断/レビュー観点）\n" + (mem or "(なし)") + "\n"
            )
            brief_msg = digest_agent.run(user_prompt=digest_prompt, model=model, backend=backend)
            append_memory(root, lead.id, f"brief: {msg.title}", brief_msg.content)

            _set(root, status_path, lead.id, lead.name or lead.id, "working", "assign worker")
            deliver_markdown(
                root=root,
                from_agent=lead.id,
                to_agent=worker.id,
                kind="worker_request",
                title=f"課長指示: {msg.title}",
                body=brief_msg.content,
            )

            archive_message(root=root, agent_id=lead.id, message_path=p)
            _set(root, status_path, lead.id, lead.name or lead.id, "idle", "")
            continue

        if msg.kind == "impl_result":
            _set(root, status_path, lead.id, lead.name or lead.id, "working", "assist request")

            diff_compact = compact_for_prompt(
                msg.body,
                stage="lead_review_diff",
                max_chars=runtime.compress.max_chars_default,
                enabled=runtime.compress.enabled,
            )

            # ask peer review lead for assistance (async). Proceed without blocking.
            peer = org.find("dev_rev_lead")
            if peer is not None:
                deliver_markdown(
                    root=root,
                    from_agent=lead.id,
                    to_agent=peer.id,
                    kind="assist_request",
                    title=f"レビュー協力依頼: {msg.title}",
                    body=(
                        "あなたはレビュー課長です。以下の差分(圧縮)を見て、\n"
                        "重大な懸念点/見落とし/確認項目を短く箇条書きで返してください。\n\n"
                        + diff_compact
                    ),
                )

            _set(root, status_path, lead.id, lead.name or lead.id, "working", "review")

            reviewer = UsagiAgent(
                name=lead.name or lead.id,
                role="reviewer",
                system_prompt=(
                    "あなたは課長(lead)でレビュー責任者です。\n"
                    "ワーカーの差分をレビューし、承認する場合は必ず 'APPROVE' と書き、\n"
                    "差戻しなら 'CHANGES_REQUESTED' と書いてください。"
                ),
            )
            prompt = f"ワーカー差分(圧縮):\n\n{diff_compact}\n\n判断: APPROVE / CHANGES_REQUESTED\n"
            review_msg = reviewer.run(user_prompt=prompt, model=model, backend=backend)

            # send to manager
            if mgr is not None:
                deliver_markdown(
                    root=root,
                    from_agent=lead.id,
                    to_agent=mgr.id,
                    kind="review_result",
                    title=f"レビュー結果: {msg.title}",
                    body=review_msg.content + "\n\n" + diff_compact,
                )

            archive_message(root=root, agent_id=lead.id, message_path=p)
            _set(root, status_path, lead.id, lead.name or lead.id, "idle", "")
            continue

        archive_message(root=root, agent_id=lead.id, message_path=p)


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
