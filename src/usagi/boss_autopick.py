"""Boss autopick: when everyone is idle, decide next action.

Policy (initial):
- If report.md has pending human judgement -> do nothing (wait).
- Else if TODO has unchecked items -> delegate a generic follow-up to dev_mgr.
- Else do nothing.

This is intentionally simple; can be upgraded later.
"""

from __future__ import annotations

import time
from pathlib import Path

from usagi.mailbox import deliver_markdown
from usagi.org import Organization
from usagi.report_sections import parse_section
from usagi.runtime import RuntimeMode


def _event(root: Path, msg: str) -> None:
    try:
        p = root / ".usagi" / "events.log"
        p.parent.mkdir(parents=True, exist_ok=True)
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        with p.open("a", encoding="utf-8") as f:
            f.write(f"[{ts}] {msg}\n")
    except Exception:
        return


def boss_autopick(*, root: Path, outputs_dir: Path, org: Organization, runtime: RuntimeMode) -> None:
    report = outputs_dir / "report.md"
    if not report.exists():
        return

    text = report.read_text(encoding="utf-8")

    # 1) human judgement pending?
    hj = parse_section(text, "## 人間判断が必要")
    if hj and hj.strip() and "- [ ]" in hj and "(なし)" not in hj:
        _event(root, "boss_autopick: wait (human judgement pending)")
        return

    # 2) TODO pending?
    todo = parse_section(text, "## TODO")
    if "- [ ]" in todo and "(なし)" not in todo:
        # delegate generic follow-up to dev_mgr
        dev_mgr = org.find("dev_mgr")
        if dev_mgr is None:
            return
        deliver_markdown(
            root=root,
            from_agent=runtime.boss_id,
            to_agent=dev_mgr.id,
            kind="boss_plan",
            title="次の作業を進めてください（自動再開）",
            body=(
                "outputs/report.md を確認し、未完了TODOを前に進めてください。\n"
                "必要なら課長/ワーカー/同階層へ協力依頼を出してください。\n"
            ),
        )
        _event(root, "boss_autopick: delegated follow-up to dev_mgr")
        return

    _event(root, "boss_autopick: nothing to do")
