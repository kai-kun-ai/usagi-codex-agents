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
from usagi.agent_chain import boss_handle_spec, lead_tick, manager_tick, worker_tick
from usagi.boss_tick import boss_tick
from usagi.approval_pipeline import run_approval_pipeline
from usagi.org import load_org
from usagi.runtime import load_runtime
from usagi.spec import parse_spec_markdown
from usagi.state import AgentStatus, load_status, save_status
from usagi.validate import validate_spec
from usagi.report_state import update_boss_report


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
        inputs_dir: Path,
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
        self.inputs_dir = inputs_dir
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
                try:
                    self._process(job)
                except Exception as e:  # noqa: BLE001
                    # ここで落ちるとワーカースレッドが死んで入力が進まなくなる。
                    # 例外はイベントログ/詳細ログに残して継続する。
                    self._event(f"worker crash: {type(e).__name__}: {e}")
                    import logging
                    import traceback

                    logging.getLogger(__name__).error("watch worker crashed", exc_info=True)
                    self._event(traceback.format_exc())
            finally:
                self.q.task_done()

    def _process(self, job: WatchJob) -> None:
        p = job.path
        if p.suffix.lower() != ".md":
            return
        if not p.exists():
            return

        file_stat = p.stat()
        prev = self.state.last_mtime_ns(p)
        if file_stat.st_mtime_ns <= prev:
            return

        raw_text = p.read_text(encoding="utf-8")
        try:
            spec = parse_spec_markdown(raw_text)
        except Exception:
            # パースそのものが壊れた場合 → 読み込みエラー
            report = (
                "# usagi watch: 読み込みエラー\n\n"
                "入力ファイルを解釈できませんでした。\n\n"
                "## 元の内容\n\n```\n" + raw_text + "\n```\n"
            )
            self._write_report(p, report)
            self.state.set_mtime_ns(p, file_stat.st_mtime_ns)
            self.state.save()
            return

        # 項目不足でも AI に咀嚼させるため strict=False
        vr = validate_spec(spec)
        if vr.warnings:
            self._event(
                f"warnings ({p.name}): "
                + "; ".join(vr.warnings)
            )
        # spec の objective/tasks が空でも続行（AIが推測する）
        if not spec.objective and not spec.tasks and not raw_text.strip():
            # 本当に空の場合だけ弾く
            report = (
                "# usagi watch: 読み込みエラー\n\n"
                "入力ファイルが空です。\n"
            )
            self._write_report(p, report)
            self.state.set_mtime_ns(p, file_stat.st_mtime_ns)
            self.state.save()
            return

        # objective/tasks が空の場合、raw_text 全体を objective に入れる
        if not spec.objective:
            spec.objective = raw_text.strip()

        # 作業ディレクトリ（git ルートは1つに統一）
        project = spec.project or "default"
        job_id = f"{int(time.time())}-{p.stem}"
        project_dir = self.work_root
        workdir = project_dir / "jobs" / job_id
        workdir.mkdir(parents=True, exist_ok=True)

        # report出力用
        self._current_workdir = workdir  # type: ignore[attr-defined]

        # announce + status
        announce("社長うさぎ", f"開始: {p.name}")
        self._event(f"開始: {p.name}")
        if self.status_path is not None:
            status_store = load_status(self.status_path)
            status_store.set(
                AgentStatus(agent_id="boss", name="社長うさぎ", state="working", task=p.name)
            )
            save_status(self.status_path, status_store)

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

        org_file = self.org_path or Path("examples/org.toml")
        runtime_file = self.runtime_path or Path("usagi.runtime.toml")
        runtime = load_runtime(runtime_file)

        # 意思決定者(boss/manager/lead/取締役会)はホスト側で実行。
        # workerの実装ステップだけコンテナに委譲（pipeline内部で判断）。
        try:
            self._event(
                "pipeline start: "
                f"project={project} job_id={job_id} offline={True if self.dry_run else self.offline} "
                f"use_worker_container={runtime.use_worker_container}"
            )
            # Boss step only: plan + delegate via mailbox.
            boss_handle_spec(
                root=self.outputs_dir.parent,
                outputs_dir=self.outputs_dir,
                status_path=self.status_path,
                org=load_org(org_file),
                runtime=runtime,
                spec=spec,
                model=self.model,
                offline=True if self.dry_run else self.offline,
                workdir=workdir,
                input_rel=str(p.relative_to(self.inputs_dir)) if self.inputs_dir in p.parents else p.name,
                job_id=job_id,
            )
            self._event("boss delegated")
        except Exception as e:  # noqa: BLE001
            import traceback

            tb = traceback.format_exc()
            self._event(f"pipeline error: {type(e).__name__}: {e}")
            report = (
                "# usagi watch: 実行エラー\n\n"
                "パイプライン実行中に例外が発生しました。\n\n"
                "## 例外\n\n"
                f"- type: {type(e).__name__}\n"
                f"- message: {e}\n\n"
                "## traceback\n\n"
                "```\n" + tb + "\n```\n"
            )
            self._write_report(p, report)
            announce("社長うさぎ", f"失敗: {p.name}")
        finally:
            announce("社長うさぎ", f"終了: {p.name}")
            self._event(f"終了: {p.name}")
            if self.status_path is not None:
                status_store = load_status(self.status_path)
                status_store.set(AgentStatus(agent_id="boss", name="社長うさぎ", state="idle", task=""))
                save_status(self.status_path, status_store)

            # mtime更新は、最後に必ず行う（st変数の上書きを避ける）
            self.state.set_mtime_ns(p, file_stat.st_mtime_ns)
            self.state.save()

        # inputs の後処理
        runtime2 = load_runtime(self.runtime_path)
        if runtime2.input_postprocess == "trash":
            self._trash_input(p)

    def _event(self, msg: str) -> None:
        if self.event_log_path is None:
            return
        self.event_log_path.parent.mkdir(parents=True, exist_ok=True)
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        with self.event_log_path.open("a", encoding="utf-8") as f:
            f.write(f"[{ts}] {msg}\n")

    def _write_report(self, src: Path, report: str, *, spec=None, job_id: str = "", messages=None) -> Path:
        """outputs/report.md を更新する（社長用の状態ファイル）。"""

        try:
            rel_src = str(src.relative_to(self.inputs_dir))
        except Exception:
            rel_src = src.name

        workdir = None
        try:
            workdir = self._current_workdir  # type: ignore[attr-defined]
        except Exception:
            workdir = None

        # spec が無い場合は従来通り追記だけ
        if spec is None or workdir is None:
            self.outputs_dir.mkdir(parents=True, exist_ok=True)
            out = self.outputs_dir / "report.md"
            with out.open("a", encoding="utf-8") as f:
                f.write("\n\n---\n")
                f.write(f"## {time.strftime('%Y-%m-%d %H:%M:%S')} input: {rel_src}\n\n")
                f.write(report.rstrip() + "\n")
            return out

        return update_boss_report(
            outputs_dir=self.outputs_dir,
            spec=spec,
            job_id=job_id or src.stem,
            workdir=workdir,
            input_rel=rel_src,
            messages=messages,
            note="",
        )

    def _trash_input(self, p: Path) -> None:
        """処理済み入力を .usagi/trash/inputs に移動する（復元可能）。"""
        try:
            rel = p.relative_to(self.inputs_dir)
        except Exception:
            rel = Path(p.name)

        trash_root = self.inputs_dir.parent / ".usagi" / "trash" / "inputs"
        dst = trash_root / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        try:
            p.replace(dst)
            self._event(f"input trashed: {rel}")
        except Exception:
            self._event(f"input trash failed: {p.name}")


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
    worker_pool_size: int = 5,
    stop_file: Path | None = None,
    status_path: Path | None = None,
    event_log_path: Path | None = None,
) -> None:
    q: queue.Queue[WatchJob] = queue.Queue()
    state = StateStore(state_path)
    enq = DebouncedEnqueuer(q, debounce_seconds=debounce_seconds, event_log_path=event_log_path)

    runtime = load_runtime(runtime_path)

    # 起動時にAPI疎通などを試す（失敗してもwatch自体は継続）
    from usagi.startup_check import run_startup_check

    run_startup_check(runtime=runtime, model=model, offline=offline, event_log_path=event_log_path)

    pool_size = int(worker_pool_size or runtime.worker_pool_size or 5)
    pool_size = max(1, min(pool_size, 20))

    workers: list[WatchWorker] = []
    threads: list[threading.Thread] = []
    for _i in range(pool_size):
        w = WatchWorker(
            q,
            inputs_dir=inputs_dir,
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
        workers.append(w)
        t = threading.Thread(target=w.run_forever, daemon=True)
        t.start()
        threads.append(t)

    inputs_dir.mkdir(parents=True, exist_ok=True)
    scan_inputs(inputs_dir, enq)

    obs = Observer()
    obs.schedule(_Handler(enq), str(inputs_dir), recursive=recursive)
    obs.start()

    # mailbox chain: repo root is the same root as inputs/outputs
    root = outputs_dir.parent

    try:
        while True:
            if stop_file is not None and stop_file.exists():
                break

            # mailbox chain ticks (best-effort)
            try:
                org = load_org(org_path or Path("examples/org.toml"))
                runtime = load_runtime(runtime_path or Path("usagi.runtime.toml"))
                manager_tick(
                    root=root,
                    outputs_dir=outputs_dir,
                    status_path=status_path,
                    org=org,
                    runtime=runtime,
                    model=model,
                    offline=offline,
                    repo_root=work_root,
                )
                lead_tick(
                    root=root,
                    status_path=status_path,
                    org=org,
                    runtime=runtime,
                    model=model,
                    offline=offline,
                )
                worker_tick(
                    root=root,
                    status_path=status_path,
                    org=org,
                    runtime=runtime,
                    model=model,
                    offline=offline,
                    repo_root=work_root,
                )
                boss_tick(root=root, outputs_dir=outputs_dir, status_path=status_path)
            except Exception:
                pass

            time.sleep(0.5)
    except KeyboardInterrupt:
        for w in workers:
            w.stop()
        obs.stop()
    finally:
        for w in workers:
            w.stop()
        obs.stop()
        obs.join()
