from __future__ import annotations

from dataclasses import dataclass, field

import yaml


@dataclass
class Agent:
    name: str
    role: str  # planner|coder|reviewer


@dataclass
class UsagiSpec:
    project: str = "usagi-project"
    objective: str = ""
    context: str = ""
    tasks: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    agents: list[Agent] = field(
        default_factory=lambda: [
            Agent(name="社長うさぎ", role="planner"),
            Agent(name="実装うさぎ", role="coder"),
            Agent(name="監査うさぎ", role="reviewer"),
        ]
    )


def parse_spec_markdown(md: str) -> UsagiSpec:
    frontmatter, body = _extract_frontmatter(md)
    front: dict = yaml.safe_load(frontmatter) if frontmatter else {}

    objective = _pick_section(body, ["目的", "Objective"])
    context = _pick_section(body, ["背景", "Context"])
    tasks = _pick_bullets(body, ["やること", "Tasks"])
    constraints = _pick_bullets(body, ["制約", "Constraints"])

    project = str(front.get("project", "usagi-project"))

    return UsagiSpec(
        project=project,
        objective=objective,
        context=context,
        tasks=tasks,
        constraints=constraints,
    )


def _extract_frontmatter(md: str) -> tuple[str | None, str]:
    if md.startswith("---\n"):
        parts = md.split("\n---\n", 1)
        if len(parts) == 2:
            fm = parts[0].removeprefix("---\n")
            return fm, parts[1]
    return None, md


def _pick_section(body: str, names: list[str]) -> str:
    lines = body.splitlines()
    # find first heading matching names
    start = None
    level = None
    for i, line in enumerate(lines):
        if not line.startswith("#"):
            continue
        hashes, title = _split_heading(line)
        if hashes is None:
            continue
        if title in names:
            start = i + 1
            level = len(hashes)
            break
    if start is None or level is None:
        return ""

    out: list[str] = []
    for line in lines[start:]:
        if line.startswith("#"):
            hashes, _t = _split_heading(line)
            if hashes is not None and len(hashes) <= level:
                break
        out.append(line)
    return "\n".join(out).strip()


def _split_heading(line: str) -> tuple[str | None, str]:
    s = line.strip()
    if not s.startswith("#"):
        return None, ""
    hashes = s.split(" ", 1)[0]
    title = s[len(hashes) :].strip()
    if not title:
        return None, ""
    return hashes, title


def _pick_bullets(body: str, section_names: list[str]) -> list[str]:
    sec = _pick_section(body, section_names)
    if not sec:
        return []
    out: list[str] = []
    for line in sec.splitlines():
        stripped = line.strip()
        if stripped.startswith("- "):
            out.append(stripped.removeprefix("- ").strip())
        elif stripped.startswith("* "):
            out.append(stripped.removeprefix("* ").strip())
    return out
