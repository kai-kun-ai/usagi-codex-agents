"""Boss inbox handler for mailbox chain."""

from __future__ import annotations

from pathlib import Path

from usagi.mailbox import archive_message, list_inbox
from usagi.mailbox_parse import parse_mail_markdown
from usagi.report_state import update_boss_report
from usagi.spec import UsagiSpec
from usagi.state import AgentStatus, load_status, save_status


def boss_tick(*, root: Path, outputs_dir: Path, status_path: Path | None) -> None:
    boss_id = "boss"

    for p in list_inbox(root=root, agent_id=boss_id):
        msg = parse_mail_markdown(p.read_text(encoding="utf-8"))
        if msg.kind not in {"manager_report", "share"}:
            archive_message(root=root, agent_id=boss_id, message_path=p)
            continue

        if status_path is not None:
            st = load_status(status_path)
            st.set(AgentStatus(agent_id=boss_id, name="社長うさぎ", state="working", task="report"))
            save_status(status_path, st)

        # Update report.md as boss memory
        spec = UsagiSpec(project="usagi-project", objective=msg.title, tasks=[], constraints=[], context="")
        update_boss_report(
            outputs_dir=outputs_dir,
            spec=spec,
            job_id=p.stem,
            workdir=root,
            input_rel=msg.title,
            messages=None,
            note=f"社長: 報告受領 kind={msg.kind} from={msg.from_agent}",
            boss_summary=msg.title,
            boss_decisions=[],
        )

        archive_message(root=root, agent_id=boss_id, message_path=p)

        if status_path is not None:
            st = load_status(status_path)
            st.set(AgentStatus(agent_id=boss_id, name="社長うさぎ", state="idle", task=""))
            save_status(status_path, st)
