"""boss inbox: Discordメンションや外部入力をbossのinputとして保存する。

現段階ではファイルベース:
- `.usagi/inbox/` に 1メッセージ=1ファイル で保存

後続で、watch/autopilot がここを入力として処理できるように統合する。
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path


@dataclass
class BossInput:
    source: str
    text: str


def write_boss_input(root: Path, inp: BossInput) -> Path:
    inbox = root / ".usagi" / "inbox"
    inbox.mkdir(parents=True, exist_ok=True)
    name = f"{int(time.time())}-{inp.source}.txt"
    p = inbox / name
    p.write_text(inp.text, encoding="utf-8")
    return p
