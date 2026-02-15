"""統合CUI（管理画面）。

狙い:
- サブコマンドで分散している watch/autopilot/status を1つの画面に集約
- 稼働状況（.usagi/status.json / .usagi/events.log）をライブ表示

注意:
- まずは最小構成（start/stop + 状態表示 + イベントログ）
- watch は同一プロセス内で thread 起動（安定優先）
"""

from __future__ import annotations

import threading
from pathlib import Path

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal
from textual.widgets import Button, Footer, Header, Static

from usagi.autopilot import clear_stop, request_stop, stop_requested
from usagi.state import load_status
from usagi.watch import watch_inputs


class _StatusBox(Static):
    def update_text(self, root: Path) -> None:
        stop = "STOP_REQUESTED" if stop_requested(root) else "RUNNING"
        st = load_status(root / ".usagi/status.json")
        lines = [f"mode: {stop}"]
        if st.agents:
            lines.append("")
            lines.append("agents:")
            for a in st.agents.values():
                task = f" {a.task}" if a.task else ""
                lines.append(f"- {a.name} ({a.agent_id}): {a.state}{task}")
        else:
            lines.append("(no status)")
        self.update("\n".join(lines))


class _EventsBox(Static):
    def update_text(self, log_path: Path, max_lines: int = 30) -> None:
        if not log_path.exists():
            self.update("(no events yet)")
            return
        try:
            lines = log_path.read_text(encoding="utf-8").splitlines()
        except Exception:
            self.update("(failed to read events)")
            return
        tail = lines[-max_lines:]
        self.update("\n".join(tail) if tail else "(no events yet)")


class UsagiTui(App):
    CSS = """
    #main { height: 1fr; }
    #left, #right { width: 1fr; }
    #events { height: 1fr; }
    #status { height: 1fr; }
    """

    BINDINGS = [
        ("s", "toggle", "Start/Stop"),
        ("q", "quit", "Quit"),
    ]

    def __init__(self, *, root: Path, model: str, offline: bool) -> None:
        super().__init__()
        self.root = root
        self.model = model
        self.offline = offline

        self._watch_thread: threading.Thread | None = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Container(id="main"):
            with Horizontal():
                with Container(id="left"):
                    yield Static("操作", classes="box")
                    yield Button("Start (clear STOP)", id="start")
                    yield Button("Stop (create STOP)", id="stop")
                with Container(id="right"):
                    yield Static("状態", classes="box")
                    yield _StatusBox(id="status")
            yield Static("イベントログ", classes="box")
            yield _EventsBox(id="events")
        yield Footer()

    def on_mount(self) -> None:
        self.set_interval(0.5, self._refresh)

    def _ensure_watch_thread(self) -> None:
        if self._watch_thread is not None and self._watch_thread.is_alive():
            return

        def _run() -> None:
            # watchはSTOPファイルがあると即終了する
            watch_inputs(
                inputs_dir=self.root / "inputs",
                outputs_dir=self.root / "outputs",
                work_root=self.root / "work",
                state_path=self.root / ".usagi/state.json",
                debounce_seconds=0.25,
                model=self.model,
                dry_run=False,
                offline=self.offline,
                recursive=True,
                stop_file=self.root / ".usagi/STOP",
                status_path=self.root / ".usagi/status.json",
                event_log_path=self.root / ".usagi/events.log",
            )

        t = threading.Thread(target=_run, daemon=True)
        t.start()
        self._watch_thread = t

    def _refresh(self) -> None:
        self.query_one(_StatusBox).update_text(self.root)
        self.query_one(_EventsBox).update_text(self.root / ".usagi/events.log")

        # RUNNINGならwatchスレッドを維持
        if not stop_requested(self.root):
            self._ensure_watch_thread()

    def action_toggle(self) -> None:
        if stop_requested(self.root):
            clear_stop(self.root)
        else:
            request_stop(self.root)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "start":
            clear_stop(self.root)
        if event.button.id == "stop":
            request_stop(self.root)


def run_tui(*, root: Path, model: str, offline: bool) -> None:
    # events.logが読めるように最低限作っておく
    (root / ".usagi").mkdir(parents=True, exist_ok=True)
    # Textual起動
    UsagiTui(root=root, model=model, offline=offline).run()
