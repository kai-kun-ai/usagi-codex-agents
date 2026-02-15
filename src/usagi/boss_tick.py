"""Boss inbox handler for mailbox chain.

Boss responsibilities:
- When receiving reports, update outputs/report.md (CEO report) continuously.
- Keep a boss memory log.
- Use the org chart to summarize subordinate structure.
"""

from __future__ import annotations

import time
from pathlib import Path

from usagi.agent_memory import append_memory
from usagi.human_judgement import append_human_judgement
from usagi.mailbox import archive_message, deliver_markdown, list_inbox
from usagi.mailbox_parse import parse_mail_markdown
from usagi.org import Organization
from usagi.prompt_compact import compact_for_prompt
from usagi.report_state import update_boss_report
from usagi.runtime import RuntimeMode
from usagi.spec import UsagiSpec
from usagi.state import AgentStatus, load_status, save_status


def boss_tick(
    *,
    root: Path,
    outputs_dir: Path,
    status_path: Path | None,
    org: Organization,
    runtime: RuntimeMode,
) -> None:
    boss_id = runtime.boss_id or "boss"

    boss = org.find(boss_id)
    boss_name = boss.name if boss and boss.name else "社長うさぎ"

    for p in list_inbox(root=root, agent_id=boss_id):
        msg = parse_mail_markdown(p.read_text(encoding="utf-8"))
        if msg.kind not in {"manager_report", "share"}:
            archive_message(root=root, agent_id=boss_id, message_path=p)
            continue

        if status_path is not None:
            st = load_status(status_path)
            st.set(AgentStatus(agent_id=boss_id, name=boss_name, state="working", task="report"))
            save_status(status_path, st)

        # summarize org/subordinates
        subs = []
        if boss and boss.can_command:
            for sid in boss.can_command:
                a = org.find(sid)
                subs.append(f"{sid}({a.name if a and a.name else sid})")
        sub_summary = f"直属部下数={len(subs)}: " + ", ".join(subs)

        # extract decisions from report body (bullets)
        body_lines = msg.body.splitlines()
        bullets = [ln.strip().lstrip("-").strip() for ln in body_lines if ln.strip().startswith("-")]
        decisions = [sub_summary] + bullets[:15]

        # boss memory
        append_memory(
            root,
            boss_id,
            f"report from {msg.from_agent} kind={msg.kind}",
            compact_for_prompt(msg.body, stage="boss_memory_report", max_chars=2500, enabled=runtime.compress.enabled),
        )

        # Update report.md as CEO report
        spec = UsagiSpec(project="usagi-project", objective=msg.title, tasks=[], constraints=[], context="")
        try:
            update_boss_report(
                outputs_dir=outputs_dir,
                spec=spec,
                job_id=p.stem,
                workdir=root,
                input_rel=msg.title,
                messages=None,
                note=f"社長: 報告受領 kind={msg.kind} from={msg.from_agent}",
                boss_summary=msg.title,
                boss_decisions=decisions,
            )
            _event(root, "boss_tick: report updated")
        except Exception as e:  # noqa: BLE001
            _event(root, f"boss_tick: report update failed: {type(e).__name__}: {e}")

        # escalation hooks
        up = msg.body.upper()
        if "ESCALATE_TO_BOSS" in up:
            # ask board (vote) first
            deliver_markdown(
                root=root,
                from_agent=boss_id,
                to_agent="board",
                kind="vote_request",
                title=f"要判断: {msg.title}",
                body=compact_for_prompt(msg.body, stage="boss_to_board", max_chars=3500, enabled=runtime.compress.enabled),
            )
            append_human_judgement(
                outputs_dir=outputs_dir,
                title=f"取締役会判断待ち: {msg.title}",
                details=f"mail={p.name}",
            )

        archive_message(root=root, agent_id=boss_id, message_path=p)

        if status_path is not None:
            st = load_status(status_path)
            st.set(AgentStatus(agent_id=boss_id, name=boss_name, state="idle", task=""))
            save_status(status_path, st)


def _event(root: Path, msg: str) -> None:
    try:
        p = root / ".usagi" / "events.log"
        p.parent.mkdir(parents=True, exist_ok=True)
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        with p.open("a", encoding="utf-8") as f:
            f.write(f"[{ts}] {msg}\n")
    except Exception:
        return
