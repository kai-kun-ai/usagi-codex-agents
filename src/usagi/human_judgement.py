"""Append human-judgement requests to outputs/report.md."""

from __future__ import annotations

import time
from pathlib import Path

from usagi.report_sections import parse_section, replace_section


def append_human_judgement(*, outputs_dir: Path, title: str, details: str = "") -> Path:
    outputs_dir.mkdir(parents=True, exist_ok=True)
    report = outputs_dir / "report.md"
    text = report.read_text(encoding="utf-8") if report.exists() else "# 社長レポート\n"

    sec = parse_section(text, "## 人間判断が必要")
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    item = f"- [ ] [{ts}] {title}"
    if details.strip():
        item += f"\n  - {details.strip()}"

    if not sec.strip() or sec.strip() == "- [ ] (なし)":
        new_sec = item
    else:
        new_sec = sec.rstrip() + "\n" + item

    new_text = replace_section(text, "## 人間判断が必要", new_sec)
    report.write_text(new_text, encoding="utf-8")
    return report
