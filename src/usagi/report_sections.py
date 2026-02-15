"""Small helpers for updating/reading sections in Markdown-like documents."""

from __future__ import annotations


def parse_section(text: str, heading: str) -> str:
    """Return the body of a section (best-effort)."""

    if not text:
        return ""
    lines = text.splitlines()
    in_sec = False
    buf: list[str] = []
    for line in lines:
        if line.strip() == heading:
            in_sec = True
            continue
        if in_sec and line.startswith("## "):
            break
        if in_sec:
            buf.append(line)
    return "\n".join(buf).strip()
