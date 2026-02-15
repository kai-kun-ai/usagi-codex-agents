"""Markdown mailbox protocol (agent-to-agent async handoff).

Design goal:
- Agents exchange information ONLY via Markdown files.
- Each agent has its own inbox/outbox/notes directories under workdir.
- A handoff is done by dropping a .md file into the recipient's inbox.

Directory layout (per workdir):
- `<workdir>/.usagi/agents/<agent_id>/inbox/`
- `<workdir>/.usagi/agents/<agent_id>/outbox/`
- `<workdir>/.usagi/agents/<agent_id>/notes/`
- `<workdir>/.usagi/agents/<agent_id>/archive/` (processed inbox messages)

NOTE:
- This module intentionally does NOT run any watchers. It is pure filesystem helpers.
- Keep content free of secrets (policy is to never include secrets in logs/artifacts).
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AgentMailbox:
    root: Path
    agent_id: str

    @property
    def base(self) -> Path:
        return self.root / ".usagi" / "agents" / self.agent_id

    @property
    def inbox(self) -> Path:
        return self.base / "inbox"

    @property
    def outbox(self) -> Path:
        return self.base / "outbox"

    @property
    def notes(self) -> Path:
        return self.base / "notes"

    @property
    def archive(self) -> Path:
        return self.base / "archive"


def ensure_mailbox(root: Path, agent_id: str) -> AgentMailbox:
    mb = AgentMailbox(root=root, agent_id=agent_id)
    for d in [mb.inbox, mb.outbox, mb.notes, mb.archive]:
        d.mkdir(parents=True, exist_ok=True)
    return mb


def deliver_markdown(
    *,
    root: Path,
    from_agent: str,
    to_agent: str,
    title: str,
    body: str,
    kind: str = "message",
) -> Path:
    """Deliver a Markdown message to recipient inbox.

    Side effects:
    - Writes an event line to `<root>/.usagi/events.log` for traceability.

    Returns:
        The created file path.
    """

    ensure_mailbox(root, from_agent)
    to_mb = ensure_mailbox(root, to_agent)

    ts = time.strftime("%Y%m%d-%H%M%S")
    safe_title = _slug(title) or "message"
    p = to_mb.inbox / f"{ts}-{from_agent}-{safe_title}.md"
    p = _ensure_unique_path(p)

    content = (
        "---\n"
        f"kind: {kind}\n"
        f"from: {from_agent}\n"
        f"to: {to_agent}\n"
        f"title: {title}\n"
        f"created: {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
        "---\n\n"
        f"# {title}\n\n"
        f"{body.strip()}\n"
    )
    p.write_text(content, encoding="utf-8")

    _event(root, f"mailbox: delivered kind={kind} {from_agent} -> {to_agent}: {p.name}")
    return p


def list_inbox(*, root: Path, agent_id: str) -> list[Path]:
    mb = ensure_mailbox(root, agent_id)
    return sorted(mb.inbox.glob("*.md"))


def archive_message(*, root: Path, agent_id: str, message_path: Path) -> Path:
    """Move an inbox message into archive (processed)."""

    mb = ensure_mailbox(root, agent_id)
    dst = mb.archive / message_path.name
    dst = _ensure_unique_path(dst)
    message_path.replace(dst)
    _event(root, f"mailbox: archived {agent_id}: {dst.name}")
    return dst


def _event(root: Path, msg: str) -> None:
    try:
        p = root / ".usagi" / "events.log"
        p.parent.mkdir(parents=True, exist_ok=True)
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        with p.open("a", encoding="utf-8") as f:
            f.write(f"[{ts}] {msg}\n")
    except Exception:
        return


def _slug(s: str) -> str:
    s2 = "".join(ch.lower() if ch.isalnum() else "-" for ch in s.strip())
    while "--" in s2:
        s2 = s2.replace("--", "-")
    return s2.strip("-")


def _ensure_unique_path(p: Path) -> Path:
    if not p.exists():
        return p
    i = 2
    while True:
        cand = p.with_name(f"{p.stem}-{i}{p.suffix}")
        if not cand.exists():
            return cand
        i += 1
