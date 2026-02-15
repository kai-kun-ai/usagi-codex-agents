"""Per-agent short-term memory stored as Markdown.

We keep a simple append-only log per agent:
- `.usagi/memory/<agent_id>.md`

This is used as context for manager/lead digesting before delegating.
"""

from __future__ import annotations

import time
from pathlib import Path

from usagi.prompt_compact import compact_for_prompt


def memory_path(root: Path, agent_id: str) -> Path:
    return root / ".usagi" / "memory" / f"{agent_id}.md"


def read_memory(root: Path, agent_id: str, *, max_chars: int = 2000) -> str:
    p = memory_path(root, agent_id)
    if not p.exists():
        return ""
    try:
        text = p.read_text(encoding="utf-8")
    except Exception:
        return ""
    return compact_for_prompt(text, stage=f"memory_{agent_id}", max_chars=max_chars)


def append_memory(root: Path, agent_id: str, title: str, body: str) -> None:
    p = memory_path(root, agent_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    with p.open("a", encoding="utf-8") as f:
        f.write("\n\n---\n")
        f.write(f"## [{ts}] {title}\n\n")
        f.write(body.strip() + "\n")
