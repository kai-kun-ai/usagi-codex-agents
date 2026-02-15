"""inputs/ フォルダ監視。

- inputs_dir 配下に .md が追加/更新されたらジョブキューに投入
- デバウンスで保存連打を1回にまとめる
- 逐次ワーカーが処理して outputs_dir にレポートを書き出す
- state.json に最終処理mtimeを保存して二重処理を防ぐ

CIではinotify実機がない想定なので、Observer起動部分は薄くし、
ロジック（デバウンス/worker/state）はユニットテストで担保する。
"""

from __future__ import annotations

import json
import queue
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from usagi.announce import announce
from usagi.approval_pipeline import run_approval_pipeline
from usagi.org import load_org
from usagi.runtime import load_runtime
from usagi.spec import parse_spec_markdown
from usagi.state import AgentStatus, load_status, save_status
from usagi.validate import validate_spec


@dataclass
class WatchJob:
    path: Path


class StateStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._data: dict[str, int] = {}
        self.load()

    def load(self) -> None:
        if not self.path.exists():
            self._data = {}
            return
        self._data = json.loads(self.path.read_text(encoding="utf-8"))

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self._data, ensure_ascii=False, indent=2), encoding="utf-8")

    def last_mtime_ns(self, p: Path) -> int:
        return int(self._data.get(str(p), 0))

    def set_mtime_ns(self, p: Path, mtime_ns: int) -> None:
        self._data[str(p)] = int(mtime_ns)


class DebouncedEnqueuer:
    def __init__(
        self,
        q: queue.Queue[WatchJob],
        debounce_seconds: float,
        *,
        event_log_path: Path | None = None,
    ) -> None:
        self.q = q
        self.debounce_seconds = debounce_seconds
        self.event_log_path = event_log_path
        self._lock = threading.Lock()
        self._timers: dict[str, threading.Timer] = {}

    def enqueue(self, p: Path, reason: str = "update") -> None:
        key = str(p)
        with self._lock:
            if key in self._timers:
                self._timers[key].cancel()
            t = threading.Timer(self.debounce_seconds, self._fire, args=(p, reason))
            self._timers[key] = t
            t.start()

    def _fire(self, p: Path, reason: str) -> None:
        with self._lock:
            self._timers.pop(str(p), None)
        self._event(f"queued({reason}): {p.name}")
        self.q.put(WatchJob(path=p))

    def _event(self, msg: str) -> None:
        if self.event_log_path is None:
            return
        self.event_log_path.parent.mkdir(parents=True, exist_ok=True)
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        with self.event_log_path.open("a", encoding="utf-8") as f:
            f.write(f"[{ts}] {msg}\n")


class WatchWorker:
    def __init__(
        self,
        q: queue.Queue[WatchJob],
        *,
        outputs_dir: Path,
        work_root: Path,
        state: StateStore,
        model: str,
        dry_run: bool,
        offline: bool,
        org_path: Path | None,
        runtime_path: Path | None,
        status_path: Path | None,
        event_log_path: Path | None = None,
    ) -> None:
        self.q = q
        self.outputs_dir = outputs_dir
        self.work_root = work_root
        self.state = state
        self.model = model
        self.dry_run = dry_run
        self.offline = offline
        self._stop = threading.Event()
        self.org_path = org_path
        self.runtime_path = runtime_path
        self.status_path = status_path
        self.event_log_path = event_log_path

    def stop(self) -> None:
        self._stop.set()

    def run_forever(self) -> None:
        while not self._stop.is_set():
            try:
                job = self.q.get(timeout=0.2)
            except queue.Empty:
                continue
            try:
                self._process(job)
            finally:
                self.q.task_done()

    def _process(self, job: WatchJob) -> None:
        p = job.path
        if p.suffix.lower() != ".md":
            return
        if not p.exists():
            return

        st = p.stat()
        prev = self.state.last_mtime_ns(p)
        if st.st_mtime_ns <= prev:
            return

        spec = parse_spec_markdown(p.read_text(encoding="utf-8"))
        vr = validate_spec(spec)
        if not vr.ok:
            # write validation report and mark processed
            errors = "\n".join([f"- {e}" for e in vr.errors])
            report = "# usagi watch: validation failed\n\n" + errors + "\n"
            self._write_report(p, report)
            self.state.set_mtime_ns(p, st.st_mtime_ns)
            self.state.save()
            return

        job_id = f"{int(time.time())}-{p.stem}"
        workdir = self.work_root / job_id
        workdir.mkdir(parents=True, exist_ok=True)

        # announce + status
        announce("社長うさぎ", f"開始: {p.name}")
        self._event(f"開始: {p.name}")
        if self.status_path is not None:
            st = load_status(self.status_path)
            st.set(AgentStatus(agent_id="boss", name="社長うさぎ", state="working", task=p.name))
            save_status(self.status_path, st)

        # minimal UI for background
        class _Ui:
            def section(self, _t: str) -> None:
                return None

            def log(self, _l: str) -> None:
                return None

            def step(self, _t: str):
                return self

            def succeed(self, _m: str | None = None) -> None:
                return None

            def fail(self, _m: str | None = None) -> None:
                return None

        if self.dry_run:
            # 互換: dry-run は従来通り簡易レポート
            res = run_approval_pipeline(
                spec=spec,
                workdir=workdir,
                model=self.model,
                offline=True,
                org=load_org(self.org_path or Path("examples/org.toml")),
                runtime=load_runtime(self.runtime_path),
                root=Path("."),
            )
        else:
            res = run_approval_pipeline(
                spec=spec,
                workdir=workdir,
                model=self.model,
                offline=self.offline,
                org=load_org(self.org_path or Path("examples/org.toml")),
                runtime=load_runtime(self.runtime_path),
                root=Path("."),
            )

        self._write_report(p, res.report)

        announce("社長うさぎ", f"終了: {p.name}")
        self._event(f"終了: {p.name}")
        if self.status_path is not None:
            st = load_status(self.status_path)
            st.set(AgentStatus(agent_id="boss", name="社長うさぎ", state="idle", task=""))
            save_status(self.status_path, st)

        self.state.set_mtime_ns(p, st.st_mtime_ns)
        self.state.save()

    def _event(self, msg: str) -> None:
        if self.event_log_path is None:
            return
        self.event_log_path.parent.mkdir(parents=True, exist_ok=True)
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        with self.event_log_path.open("a", encoding="utf-8") as f:
            f.write(f"[{ts}] {msg}\n")

    def _write_report(self, src: Path, report: str) -> Path:
        self.outputs_dir.mkdir(parents=True, exist_ok=True)
        out = self.outputs_dir / f"{src.stem}.report.md"
        out.write_text(report, encoding="utf-8")
        return out


class _Handler(FileSystemEventHandler):
    def __init__(self, enq: DebouncedEnqueuer) -> None:
        self.enq = enq

    def on_created(self, event):  # type: ignore[override]
        if not event.is_directory:
            self.enq.enqueue(Path(event.src_path), reason="created")

    def on_modified(self, event):  # type: ignore[override]
        if not event.is_directory:
            self.enq.enqueue(Path(event.src_path), reason="modified")


def scan_inputs(inputs_dir: Path, enq: DebouncedEnqueuer) -> None:
    for p in inputs_dir.glob("**/*.md"):
        enq.enqueue(p, reason="scan")


def watch_inputs(
    *,
    inputs_dir: Path,
    outputs_dir: Path,
    work_root: Path,
    state_path: Path,
    debounce_seconds: float,
    model: str,
    dry_run: bool,
    offline: bool,
    recursive: bool,
    org_path: Path | None = None,
    runtime_path: Path | None = None,
    stop_file: Path | None = None,
    status_path: Path | None = None,
    event_log_path: Path | None = None,
) -> None:
    q: queue.Queue[WatchJob] = queue.Queue()
    state = StateStore(state_path)
    enq = DebouncedEnqueuer(q, debounce_seconds=debounce_seconds, event_log_path=event_log_path)

    worker = WatchWorker(
        q,
        outputs_dir=outputs_dir,
        work_root=work_root,
        state=state,
        model=model,
        dry_run=dry_run,
        offline=offline,
        org_path=org_path,
        runtime_path=runtime_path,
        status_path=status_path,
        event_log_path=event_log_path,
    )
    t = threading.Thread(target=worker.run_forever, daemon=True)
    t.start()

    inputs_dir.mkdir(parents=True, exist_ok=True)
    scan_inputs(inputs_dir, enq)

    obs = Observer()
    obs.schedule(_Handler(enq), str(inputs_dir), recursive=recursive)
    obs.start()

    try:
        while True:
            if stop_file is not None and stop_file.exists():
                break
            time.sleep(0.5)
    except KeyboardInterrupt:
        worker.stop()
        obs.stop()
    finally:
        worker.stop()
        obs.stop()
        obs.join()
