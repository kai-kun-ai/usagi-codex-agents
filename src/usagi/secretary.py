"""秘書エージェント（🐻）: 対話→ input.md 整形。

方針:
- TUI上では社長と直接チャットせず、秘書と対話する。
- 秘書は会話ログを蓄積し、ユーザーが「社長に渡す」操作をした時に
  input spec Markdown を生成して inputs/ に配置する。

最初の実装はオフラインでも動くテンプレ整形。
後続で LLM（profile指定）による整形/要約を追加する。
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path


@dataclass
class SecretaryConfig:
    root: Path
    secretary_id: str = "secretary"
    secretary_name: str = "🐻 秘書クマ"


def secretary_log_path(root: Path) -> Path:
    return root / ".usagi/secretary.log"


def append_secretary_log(root: Path, who: str, text: str) -> None:
    log = secretary_log_path(root)
    log.parent.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    with log.open("a", encoding="utf-8") as f:
        f.write(f"[{ts}] {who}: {text}\n")


def format_input_from_dialog(title: str, dialog_lines: list[str]) -> str:
    body = "\n".join(dialog_lines).strip()
    return (
        "# usagi spec\n\n"
        f"title: {title}\n\n"
        "## request\n\n"
        "以下は秘書(🐻)との対話ログから整形した依頼です。\n\n"
        f"{body}\n"
    )


def place_input_for_boss(root: Path, title: str, dialog_lines: list[str]) -> Path:
    inputs_dir = root / "inputs" / "secretary"
    inputs_dir.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%d-%H%M%S")
    p = inputs_dir / f"{ts}.md"
    p.write_text(format_input_from_dialog(title=title, dialog_lines=dialog_lines), encoding="utf-8")
    return p
