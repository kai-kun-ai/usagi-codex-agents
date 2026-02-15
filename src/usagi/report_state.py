"""outputs/report.md を「社長が読む状態ファイル」として更新する。

方針:
- 追記ログではなく、上部の TODO / 最新状況 を差分更新する。
- 履歴は直近N件のみ残す。

NOTE:
- このファイルは人間が読む前提。厳密な構文よりも壊れにくさ重視。
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

from usagi.agents import AgentMessage
from usagi.spec import UsagiSpec


@dataclass(frozen=True)
class ReportEntry:
    ts: str
    input_path: str
    project: str
    job_id: str
    workdir: str
    ok: bool
    tasks: list[str]
    note: str


def update_boss_report(*, outputs_dir: Path, spec: UsagiSpec, job_id: str, workdir: Path, input_rel: str,
                       messages: list[AgentMessage] | None, note: str) -> Path:
    """outputs/report.md を更新する。"""

    outputs_dir.mkdir(parents=True, exist_ok=True)
    out = outputs_dir / "report.md"

    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    project = spec.project or "default"

    lead_ok, merge_ok = _extract_outcome(messages or [])
    ok = bool(lead_ok and merge_ok)

    tasks = [t.strip() for t in (spec.tasks or []) if t.strip()]

    entry = ReportEntry(
        ts=ts,
        input_path=input_rel,
        project=project,
        job_id=job_id,
        workdir=str(workdir),
        ok=ok,
        tasks=tasks,
        note=note.strip(),
    )

    text = out.read_text(encoding="utf-8") if out.exists() else ""
    new_text = _merge(text, entry)
    out.write_text(new_text, encoding="utf-8")
    return out


def _extract_outcome(messages: list[AgentMessage]) -> tuple[bool, bool]:
    lead_ok = False
    merge_ok = False
    for m in messages:
        c = (m.content or "").upper()
        if m.role == "reviewer" and "APPROVE" in c:
            lead_ok = True
        if m.role == "planner" and "MERGE_OK" in c:
            merge_ok = True
    return lead_ok, merge_ok


def _merge(existing: str, entry: ReportEntry) -> str:
    todo = _parse_todo(existing)
    hist = _parse_history(existing)

    # TODO: add new tasks
    for t in entry.tasks:
        todo.setdefault(t, False)

    # mark done on success
    if entry.ok:
        for t in entry.tasks:
            if t:
                todo[t] = True

    # append history (keep last 20)
    hist.append(entry)
    hist = hist[-20:]

    lines: list[str] = []
    lines.append("# 社長レポート")
    lines.append("")
    lines.append("## TODO")
    if not todo:
        lines.append("- [ ] (なし)")
    else:
        for t, done in sorted(todo.items(), key=lambda kv: (kv[1], kv[0])):
            lines.append(f"- [{'x' if done else ' '}] {t}")
    lines.append("")

    lines.append("## 最新状況")
    lines.append(f"- updated: {entry.ts}")
    lines.append(f"- input: {entry.input_path}")
    lines.append(f"- project: {entry.project}")
    lines.append(f"- job_id: {entry.job_id}")
    lines.append(f"- ok: {entry.ok}")
    lines.append(f"- workdir: `{entry.workdir}`")
    if entry.note:
        lines.append(f"- note: {entry.note}")
    lines.append("")

    lines.append("## 履歴（直近20）")
    for h in reversed(hist):
        lines.append("-")
        lines.append(f"  - ts: {h.ts}")
        lines.append(f"  - input: {h.input_path}")
        lines.append(f"  - project: {h.project}")
        lines.append(f"  - job_id: {h.job_id}")
        lines.append(f"  - ok: {h.ok}")
        if h.note:
            lines.append(f"  - note: {h.note}")
    lines.append("")

    return "\n".join(lines)


def _parse_todo(existing: str) -> dict[str, bool]:
    todo: dict[str, bool] = {}
    in_todo = False
    for line in existing.splitlines():
        if line.strip() == "## TODO":
            in_todo = True
            continue
        if in_todo and line.startswith("## "):
            break
        if not in_todo:
            continue
        s = line.strip()
        if s.startswith("- [x] "):
            todo[s[len("- [x] "):]] = True
        elif s.startswith("- [ ] "):
            todo[s[len("- [ ] "):]] = False
    # drop placeholder
    todo.pop("(なし)", None)
    return todo


def _parse_history(existing: str) -> list[ReportEntry]:
    # best-effort parse from the current format; if it fails, return empty
    if "## 履歴" not in existing:
        return []
    # We only parse minimal fields; if format changes, history resets.
    entries: list[ReportEntry] = []
    current: dict[str, str] = {}
    in_hist = False
    for line in existing.splitlines():
        if line.strip().startswith("## 履歴"):
            in_hist = True
            continue
        if not in_hist:
            continue
        if line.strip() == "-":
            if current:
                entries.append(_entry_from_dict(current))
                current = {}
            continue
        s = line.strip()
        if s.startswith("- ") and ":" in s:
            k, v = s[2:].split(":", 1)
            current[k.strip()] = v.strip()
    if current:
        entries.append(_entry_from_dict(current))
    return [e for e in entries if e.ts]


def _entry_from_dict(d: dict[str, str]) -> ReportEntry:
    return ReportEntry(
        ts=d.get("ts", ""),
        input_path=d.get("input", ""),
        project=d.get("project", ""),
        job_id=d.get("job_id", ""),
        workdir="",
        ok=d.get("ok", "false").lower() == "true",
        tasks=[],
        note=d.get("note", ""),
    )
