from pathlib import Path

from usagi.boss_inbox import BossInput, write_boss_input


def test_tui_chat_writes_inbox(tmp_path: Path) -> None:
    p = write_boss_input(tmp_path, BossInput(source="tui", text="hi"))
    assert p.exists()
    assert p.read_text(encoding="utf-8") == "hi"
