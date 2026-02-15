import queue
from pathlib import Path

from usagi.watch import DebouncedEnqueuer, WatchJob


def test_debounced_enqueuer_writes_event(tmp_path: Path) -> None:
    q: queue.Queue[WatchJob] = queue.Queue()
    log = tmp_path / "events.log"
    enq = DebouncedEnqueuer(q, debounce_seconds=0.0, event_log_path=log)

    p = tmp_path / "a.md"
    p.write_text("x", encoding="utf-8")

    enq.enqueue(p, reason="test")
    job = q.get(timeout=1)
    assert job.path == p
    assert log.exists()
    assert "queued(test)" in log.read_text(encoding="utf-8")
