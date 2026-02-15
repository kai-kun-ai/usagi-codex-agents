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


def replace_section(text: str, heading: str, body: str) -> str:
    """Replace or insert a section (best-effort).

    - If heading exists, replaces its body until the next `## ` heading.
    - If not, appends at end.
    """

    lines = (text or "").splitlines()
    out: list[str] = []
    i = 0
    found = False
    while i < len(lines):
        line = lines[i]
        if line.strip() == heading:
            found = True
            out.append(line)
            # write new body
            if body:
                out.extend(body.splitlines())
            # skip old body
            i += 1
            while i < len(lines) and not lines[i].startswith("## "):
                i += 1
            continue
        out.append(line)
        i += 1

    if not found:
        if out and out[-1].strip() != "":
            out.append("")
        out.append(heading)
        if body:
            out.extend(body.splitlines())

    return "\n".join(out).rstrip() + "\n"
