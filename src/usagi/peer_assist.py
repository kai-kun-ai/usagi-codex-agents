"""Peer assist handlers (same-layer cooperation)."""

from __future__ import annotations

from pathlib import Path

from usagi.agents import CodexCLIBackend, OfflineBackend, UsagiAgent
from usagi.agent_memory import append_memory, read_memory
from usagi.mailbox import archive_message, deliver_markdown, list_inbox
from usagi.mailbox_parse import parse_mail_markdown
from usagi.org import Organization
from usagi.prompt_compact import compact_for_prompt
from usagi.runtime import RuntimeMode
from usagi.state import AgentStatus, load_status, save_status


def assist_tick(
    *,
    root: Path,
    status_path: Path | None,
    org: Organization,
    runtime: RuntimeMode,
    model: str,
    offline: bool,
    agent_id: str,
    role_hint: str,
) -> None:
    """Generic handler for assist_request -> assist_response."""

    a = org.find(agent_id)
    if a is None:
        return

    backend = OfflineBackend() if offline else CodexCLIBackend()

    for p in list_inbox(root=root, agent_id=agent_id):
        msg = parse_mail_markdown(p.read_text(encoding="utf-8"))
        if msg.kind != "assist_request":
            archive_message(root=root, agent_id=agent_id, message_path=p)
            continue

        if status_path is not None:
            st = load_status(status_path)
            st.set(AgentStatus(agent_id=agent_id, name=a.name or agent_id, state="working", task="assist"))
            save_status(status_path, st)

        mem = read_memory(root, agent_id, max_chars=1500)
        agent = UsagiAgent(
            name=a.name or agent_id,
            role="reviewer",
            system_prompt=(
                f"あなたは{role_hint}です。\n"
                "依頼内容を読み、リスク/懸念/追加確認/代替案を短く返してください。\n"
                "出力は箇条書き中心で。"
            ),
        )
        prompt = (
            "## 依頼\n" + compact_for_prompt(msg.body, stage=f"assist_req_{agent_id}", max_chars=2500, enabled=runtime.compress.enabled) + "\n\n"
            "## あなたのメモリ\n" + (mem or "(なし)")
        )
        resp = agent.run(user_prompt=prompt, model=model, backend=backend)
        append_memory(root, agent_id, f"assist for {msg.from_agent}", resp.content)

        deliver_markdown(
            root=root,
            from_agent=agent_id,
            to_agent=msg.from_agent or "boss",
            kind="assist_response",
            title=f"協力返信: {msg.title}",
            body=resp.content,
        )

        archive_message(root=root, agent_id=agent_id, message_path=p)

        if status_path is not None:
            st = load_status(status_path)
            st.set(AgentStatus(agent_id=agent_id, name=a.name or agent_id, state="idle", task=""))
            save_status(status_path, st)
