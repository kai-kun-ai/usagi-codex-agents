from pathlib import Path

from usagi.runtime import RuntimeMode
from usagi.startup_check import run_startup_check


def test_startup_check_offline_noop(tmp_path: Path) -> None:
    rt = RuntimeMode()
    log = tmp_path / "events.log"
    run_startup_check(runtime=rt, model="codex", offline=True, event_log_path=log)
    assert log.read_text(encoding="utf-8").strip() != ""
