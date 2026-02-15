"""Parse mailbox markdown frontmatter."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MailMessage:
    kind: str
    title: str
    from_agent: str
    to_agent: str
    body: str


def parse_mail_markdown(text: str) -> MailMessage:
    """Best-effort YAML-frontmatter parse for mailbox messages."""

    t = text or ""
    kind = "message"
    title = ""
    from_agent = ""
    to_agent = ""

    body = t
    if t.lstrip().startswith("---"):
        parts = t.split("---", 2)
        if len(parts) >= 3:
            fm = parts[1]
            body = parts[2].lstrip("\n")
            for line in fm.splitlines():
                if ":" not in line:
                    continue
                k, v = line.split(":", 1)
                k = k.strip()
                v = v.strip()
                if k == "kind":
                    kind = v
                elif k == "title":
                    title = v
                elif k == "from":
                    from_agent = v
                elif k == "to":
                    to_agent = v

    if not title:
        # fallback: first heading
        for line in body.splitlines():
            if line.startswith("# "):
                title = line[2:].strip()
                break

    return MailMessage(kind=kind, title=title, from_agent=from_agent, to_agent=to_agent, body=body.strip())
