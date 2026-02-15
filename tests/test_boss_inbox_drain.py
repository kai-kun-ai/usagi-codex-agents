"""boss_inbox drain のテスト。"""

from pathlib import Path

from usagi.boss_inbox import BossInput, drain_boss_inbox_to_inputs, write_boss_input


def test_drain_boss_inbox_to_inputs_creates_md_and_trashes_txt(tmp_path: Path) -> None:
    root = tmp_path
    inputs_dir = root / "inputs"

    p = write_boss_input(root, BossInput(source="discord_mention", text="hello world"))
    assert p.exists()

    created = drain_boss_inbox_to_inputs(root=root, inputs_dir=inputs_dir, event_log_path=None)
    assert len(created) == 1
    md = created[0]
    assert md.exists()
    body = md.read_text(encoding="utf-8")
    assert "## 目的" in body
    assert "hello world" in body

    # 元txtはtrashへ
    assert not p.exists()
    trash = root / ".usagi" / "trash" / "inbox"
    trashed = list(trash.glob("*.txt"))
    assert len(trashed) == 1


def test_drain_boss_inbox_to_inputs_empty_is_trashed(tmp_path: Path) -> None:
    root = tmp_path
    inputs_dir = root / "inputs"

    p = write_boss_input(root, BossInput(source="discord_mention", text="\n\n"))
    assert p.exists()

    created = drain_boss_inbox_to_inputs(root=root, inputs_dir=inputs_dir, event_log_path=None)
    assert created == []

    assert not p.exists()
    trash = root / ".usagi" / "trash" / "inbox"
    trashed = list(trash.glob("*.txt"))
    assert len(trashed) == 1
