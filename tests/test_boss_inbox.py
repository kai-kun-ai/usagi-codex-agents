"""boss_inbox のテスト。"""

from pathlib import Path

from usagi.boss_inbox import BossInput, write_boss_input


def test_write_boss_input(tmp_path: Path) -> None:
    p = write_boss_input(tmp_path, BossInput(source="discord", text="hello"))
    assert p.exists()
    assert "hello" in p.read_text(encoding="utf-8")
