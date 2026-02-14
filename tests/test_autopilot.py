"""autopilot のテスト。"""

from pathlib import Path

from usagi.autopilot import clear_stop, request_stop, stop_requested


def test_stop_file_cycle(tmp_path: Path) -> None:
    assert stop_requested(tmp_path) is False

    p = request_stop(tmp_path)
    assert p.exists()
    assert stop_requested(tmp_path) is True

    clear_stop(tmp_path)
    assert stop_requested(tmp_path) is False
