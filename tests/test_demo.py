from pathlib import Path

from usagi.demo import DemoConfig, run_demo_forever


def test_demo_stops_on_stop_file(tmp_path: Path) -> None:
    # Prepare stop file so demo exits quickly
    stop = tmp_path / ".usagi" / "STOP"
    stop.parent.mkdir(parents=True, exist_ok=True)
    stop.write_text("stop", encoding="utf-8")

    run_demo_forever(DemoConfig(root=tmp_path, interval_seconds=0.01))

    # Should have written at least one event line
    log = tmp_path / ".usagi" / "events.log"
    assert log.exists()
    assert "demo halted" in log.read_text(encoding="utf-8").lower()
