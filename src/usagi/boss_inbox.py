"""boss inbox: Discordメンションや外部入力をbossのinputとして保存する。

現段階ではファイルベース:
- `.usagi/inbox/` に 1メッセージ=1ファイル で保存

watch/autopilot は `inputs/**/*.md` を監視するため、inbox の内容は
`inputs/` に変換してからキューに流す。
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
    """boss宛入力を `.usagi/inbox/*.txt` に保存する。"""
    inbox = root / ".usagi" / "inbox"
    inbox.mkdir(parents=True, exist_ok=True)
    name = f"{int(time.time())}-{inp.source}.txt"
    p = inbox / name
    p.write_text(inp.text, encoding="utf-8")
    return p


def drain_boss_inbox_to_inputs(
    *,
    root: Path,
    inputs_dir: Path,
    event_log_path: Path | None = None,
) -> list[Path]:
    """`.usagi/inbox/*.txt` を `inputs/inbox/*.md` に変換して移動する。

    目的:
    - Discordなどの受信→inbox保存の後に、watch/autopilot の既存フローへ流す

    成功時の動作:
    - inbox txt を md に変換して inputs 配下へ保存
    - 元 txt は `.usagi/trash/inbox/` へ移動（復元可能）

    Returns:
        生成した md ファイルパスのリスト。
    """

    inbox_dir = root / ".usagi" / "inbox"
    if not inbox_dir.exists():
        return []

    out_dir = inputs_dir / "inbox"
    out_dir.mkdir(parents=True, exist_ok=True)

    created: list[Path] = []
    for p in sorted(inbox_dir.glob("*.txt")):
        try:
            text = p.read_text(encoding="utf-8").strip()
        except Exception:
            continue
        if not text:
            _move_to_trash(root=root, p=p)
            _event(event_log_path, f"boss_inbox: empty -> trashed: {p.name}")
            continue

        stem = p.stem
        dst = out_dir / f"{stem}.md"
        dst = _ensure_unique_path(dst)

        md = (
            "# Discord/外部入力（inbox 経由）\n\n"
            "## 目的\n\n"
            f"{text}\n"
        )
        dst.write_text(md, encoding="utf-8")
        created.append(dst)

        _move_to_trash(root=root, p=p)
        _event(event_log_path, f"boss_inbox: drained: {p.name} -> {dst.relative_to(root)}")

    return created


def _ensure_unique_path(p: Path) -> Path:
    if not p.exists():
        return p
    i = 2
    while True:
        cand = p.with_name(f"{p.stem}-{i}{p.suffix}")
        if not cand.exists():
            return cand
        i += 1


def _move_to_trash(*, root: Path, p: Path) -> None:
    trash = root / ".usagi" / "trash" / "inbox"
    trash.mkdir(parents=True, exist_ok=True)
    dst = trash / p.name
    dst = _ensure_unique_path(dst)
    try:
        p.replace(dst)
    except Exception:
        return


def _event(event_log_path: Path | None, msg: str) -> None:
    if event_log_path is None:
        return
    event_log_path.parent.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    with event_log_path.open("a", encoding="utf-8") as f:
        f.write(f"[{ts}] {msg}\n")
