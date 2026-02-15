"""watch モジュールのテスト（inotifyなしでロジックのみ）。"""

import queue
import time
from pathlib import Path

from usagi.watch import DebouncedEnqueuer, StateStore, WatchJob, WatchWorker


def test_state_store_roundtrip(tmp_path: Path) -> None:
    p = tmp_path / "state.json"
    st = StateStore(p)
    f = tmp_path / "a.md"
    st.set_mtime_ns(f, 123)
    st.save()

    st2 = StateStore(p)
    assert st2.last_mtime_ns(f) == 123


def test_debounce_collapses(tmp_path: Path) -> None:
    q: queue.Queue[WatchJob] = queue.Queue()
    d = DebouncedEnqueuer(q, debounce_seconds=0.05)

    f = tmp_path / "a.md"
    d.enqueue(f)
    d.enqueue(f)
    d.enqueue(f)

    time.sleep(0.12)
    assert q.qsize() == 1


def test_worker_ignores_non_md(tmp_path: Path) -> None:
    q: queue.Queue[WatchJob] = queue.Queue()
    st = StateStore(tmp_path / "state.json")

    outputs = tmp_path / "out"
    work = tmp_path / "work"

    w = WatchWorker(
        q,
        inputs_dir=tmp_path,
        outputs_dir=outputs,
        work_root=work,
        state=st,
        model="codex",
        dry_run=True,
        offline=True,
        org_path=None,
        runtime_path=None,
        status_path=None,
    )

    p = tmp_path / "x.txt"
    p.write_text("hi", encoding="utf-8")
    w._process(WatchJob(path=p))  # noqa: SLF001

    assert not outputs.exists()


def test_worker_processes_spec_and_writes_report(tmp_path: Path) -> None:
    q: queue.Queue[WatchJob] = queue.Queue()
    st = StateStore(tmp_path / "state.json")

    outputs = tmp_path / "out"
    work = tmp_path / "work"

    w = WatchWorker(
        q,
        inputs_dir=tmp_path,
        outputs_dir=outputs,
        work_root=work,
        state=st,
        model="codex",
        dry_run=True,
        offline=True,
        org_path=None,
        runtime_path=None,
        status_path=None,
    )

    spec = tmp_path / "job.md"
    spec.write_text(
        """---
project: demo
---

## 目的

テスト

## やること

- README.md を作る

## 制約

- 日本語
""",
        encoding="utf-8",
    )

    w._process(WatchJob(path=spec))  # noqa: SLF001

    rep = outputs / "job.report.md"
    assert rep.exists()
    assert "うさぎさん株式会社レポート" in rep.read_text(encoding="utf-8")
