"""統合CUI（管理画面）。

狙い:
- サブコマンドで分散している watch/autopilot/status を1つの画面に集約
- 稼働状況（.usagi/status.json / .usagi/events.log）をライブ表示

注意:
- まずは最小構成（start/stop + 状態表示 + イベントログ）
- watch は同一プロセス内で thread 起動（安定優先）
"""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, VerticalScroll
from textual.widgets import Button, Footer, Header, Input, Static

from usagi.autopilot import clear_stop, request_stop, stop_requested
from usagi.boss_inbox import BossInput, write_boss_input
from usagi.demo import DemoConfig, run_demo_forever
from usagi.display import display_name
from usagi.org import load_org
from usagi.secretary import append_secretary_log, place_input_for_boss, secretary_log_path


def _fallback_org_path(org_path: Path, root: Path) -> Path:
    """org_path が存在しない時のフォールバック。

    - make demo は /app に repo がある前提なので /app/examples/org.toml を試す
    - root 配下 examples/org.toml も試す
    """

    if org_path.exists():
        return org_path

    candidates = [
        Path("/app/examples/org.toml"),
        root / "examples/org.toml",
        Path("examples/org.toml"),
    ]
    for c in candidates:
        if c.exists():
            return c
    return org_path
from usagi.state import load_status
from usagi.watch import watch_inputs


def _mode_label(root: Path) -> str:
    return "STOPPED" if stop_requested(root) else "RUNNING"


# NOTE: 状態表示は組織図に統合したため、専用ウィンドウは廃止。
class _EventsBox(Static):
    def update_text(self, log_path: Path, max_lines: int = 15) -> None:
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


class _InputsBox(Static):
    def update_text(
        self,
        inputs_dir: Path,
        state_path: Path,
        max_items: int = 12,
    ) -> None:
        inputs_dir.mkdir(parents=True, exist_ok=True)

        # state.json: {"/abs/or/rel/path.md": mtime_ns}
        state: dict[str, int] = {}
        if state_path.exists():
            try:
                state = json.loads(state_path.read_text(encoding="utf-8"))
            except Exception:
                state = {}

        items: list[tuple[Path, int]] = []
        for p in sorted(inputs_dir.glob("**/*.md")):
            try:
                st = p.stat()
            except FileNotFoundError:
                continue
            items.append((p, int(st.st_mtime_ns)))

        items.sort(key=lambda x: x[1], reverse=True)

        lines: list[str] = []
        if not items:
            self.update("(no inputs)")
            return

        pending = 0
        for p, mtime_ns in items[:max_items]:
            last = int(state.get(str(p), 0))
            done = last >= mtime_ns
            if not done:
                pending += 1
            mark = "✅" if done else "🕒"
            # Path.is_relative_to は3.9+ だが、互換のため例外で対応
            try:
                name = str(p.relative_to(inputs_dir))
            except Exception:
                name = p.name
            lines.append(f"{mark} {name}")

        header = f"inputs (pending={pending})"
        self.update(header + "\n\n" + "\n".join(lines))


class _BossChatBox(Static):
    def update_text(self, log_path: Path, max_lines: int = 25) -> None:
        if not log_path.exists():
            self.update("(no messages)")
            return
        try:
            lines = log_path.read_text(encoding="utf-8").splitlines()
        except Exception:
            self.update("(failed to read chat log)")
            return
        tail = lines[-max_lines:]
        self.update("\n".join(tail) if tail else "(no messages)")


class _SecretaryChatBox(Static):
    def update_text(self, root: Path, max_lines: int = 25) -> None:
        log_path = secretary_log_path(root)
        if not log_path.exists():
            self.update("(秘書ログなし)")
            return
        try:
            lines = log_path.read_text(encoding="utf-8").splitlines()
        except Exception:
            self.update("(failed to read secretary log)")
            return
        tail = lines[-max_lines:]
        self.update("\n".join(tail) if tail else "(秘書ログなし)")


class _OrgBox(Static):
    def update_text(self, org_path: Path, status_path: Path) -> None:
        if not org_path.exists():
            self.update("(no org.toml)")
            return

        try:
            org = load_org(org_path)
        except Exception:
            self.update("(failed to load org.toml)")
            return

        st = load_status(status_path)

        roots = [a for a in org.agents if not a.reports_to]

        def line_for(agent_id: str, name: str) -> str:
            a = st.agents.get(agent_id)
            if not a:
                return f"- {name}: unknown"
            task = f" {a.task}" if a.task else ""
            return f"- {name}: {a.state}{task}"

        lines: list[str] = []

        def walk(agent_id: str, name: str, indent: int) -> None:
            prefix = "  " * indent
            lines.append(prefix + line_for(agent_id, name))
            children = [a for a in org.agents if a.reports_to == agent_id]
            for c in children:
                walk(c.id, display_name(c), indent + 1)

        for r in roots:
            walk(r.id, display_name(r), 0)

        self.update("\n".join(lines) if lines else "(empty org)")


class UsagiTui(App):
    CSS = """
    #main { height: 1fr; }
    #left, #right { width: 1fr; }
    #events { height: 1fr; border: solid green; padding: 0 1; }
    #mode { border: solid white; background: $boost; text-style: bold; }
    /* statusウィンドウは廃止（組織図へ統合） */
    #inputs { height: auto; border: solid yellow; padding: 0 1; }
    #secretary_chat { height: 12; border: solid magenta; padding: 0 1; }
    #org_scroll { height: 1fr; border: solid blue; padding: 0 1; }
    #org { height: auto; }

    #secretary_input {
        border: heavy white;
        background: $surface;
        height: 3;
    }

    #secretary_send, #secretary_to_input {
        background: $accent;
        color: $text;
    }
    """

    BINDINGS = [
        ("ctrl+s", "toggle", "Start/Stop"),
        ("q", "quit", "Quit"),
    ]

    def __init__(
        self,
        *,
        root: Path,
        org_path: Path,
        model: str,
        offline: bool,
        demo: bool,
    ) -> None:
        super().__init__()
        self.root = root
        self.org_path = org_path
        self.model = model
        self.offline = offline
        self.demo = demo

        self._watch_thread: threading.Thread | None = None
        self._demo_thread: threading.Thread | None = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Container(id="main"):
            with Horizontal():
                with Container(id="left"):
                    mode_btn = Button("", id="mode")
                    mode_btn.border_title = "mode"
                    yield mode_btn

                    chat = _SecretaryChatBox(id="secretary_chat")
                    chat.border_title = "秘書(🐻)との対話"
                    yield chat
                    yield Input(
                        placeholder="ここに日本語で入力 → Enter で送信（例: 次のタスクを整理して）",
                        id="secretary_input",
                    )
                    yield Button("秘書へ送信", id="secretary_send")
                    yield Button("社長に渡す(input.md化)", id="secretary_to_input")

                    inputs_box = _InputsBox(id="inputs")
                    inputs_box.border_title = "入力"
                    yield inputs_box
                with Container(id="right"):
                    with VerticalScroll(id="org_scroll"):
                        org_box = _OrgBox(id="org")
                        org_box.border_title = "組織図（状態込み）"
                        yield org_box

            events_box = _EventsBox(id="events")
            events_box.border_title = "イベントログ"
            yield events_box
        yield Footer()

    def on_mount(self) -> None:
        # 入力フォーカス（秘書チャットをすぐ打てるように）
        try:
            self.query_one("#secretary_input", Input).focus()
        except Exception:
            pass

        # demoモードではwatchの代わりに疑似更新を走らせる
        if self.demo:
            self._ensure_demo_thread()
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

    def _ensure_demo_thread(self) -> None:
        if self._demo_thread is not None and self._demo_thread.is_alive():
            return

        def _run() -> None:
            run_demo_forever(
                DemoConfig(
                    root=self.root,
                    org_path=self.org_path,
                    interval_seconds=1.0,
                )
            )

        t = threading.Thread(target=_run, daemon=True)
        t.start()
        self._demo_thread = t

    def _refresh(self) -> None:
        # mode button
        self.query_one("#mode", Button).label = _mode_label(self.root)

        org_path = _fallback_org_path(self.org_path, self.root)
        self.query_one(_OrgBox).update_text(
            org_path,
            self.root / ".usagi/status.json",
        )
        self.query_one(_SecretaryChatBox).update_text(self.root)
        self.query_one(_InputsBox).update_text(
            self.root / "inputs",
            self.root / ".usagi/state.json",
        )
        self.query_one(_EventsBox).update_text(self.root / ".usagi/events.log")

        # RUNNINGならwatchスレッドを維持（demoのときはdemoスレッド）
        if not stop_requested(self.root):
            if self.demo:
                self._ensure_demo_thread()
            else:
                self._ensure_watch_thread()

    def action_toggle(self) -> None:
        if stop_requested(self.root):
            clear_stop(self.root)
        else:
            request_stop(self.root)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "mode":
            self.action_toggle()
        if event.button.id == "secretary_send":
            self._send_secretary_message()
        if event.button.id == "secretary_to_input":
            self._secretary_to_input()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "secretary_input":
            self._send_secretary_message()

    def _send_secretary_message(self) -> None:
        inp = self.query_one("#secretary_input", Input)
        text = (inp.value or "").strip()
        if not text:
            return

        append_secretary_log(self.root, who="you", text=text)

        # 簡易: 秘書からの返事は固定文（後続PRでLLM整形に差し替え）
        append_secretary_log(
            self.root,
            who="🐻 secretary",
            text="了解。社長に渡す内容として整理するね。",
        )

        inp.value = ""
        self._refresh()

    def _secretary_to_input(self) -> None:
        # secretary.log の末尾を input.md 化して inputs/ に配置
        log = secretary_log_path(self.root)
        if not log.exists():
            return

        lines = log.read_text(encoding="utf-8").splitlines()
        # 直近だけ（長すぎ防止）
        dialog = lines[-50:]
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        p = place_input_for_boss(self.root, title=f"secretary {ts}", dialog_lines=dialog)

        # 既存のboss_inbox（社長が見るべき通知）にも入れておく
        write_boss_input(
            self.root,
            BossInput(source="secretary", text=f"秘書が input を設置しました: {p}"),
        )

        events = self.root / ".usagi/events.log"
        events.parent.mkdir(parents=True, exist_ok=True)
        with events.open("a", encoding="utf-8") as f:
            f.write(f"[{ts}] secretary: placed input {p.name}\n")

        self._refresh()


def run_tui(*, root: Path, org_path: Path, model: str, offline: bool, demo: bool) -> None:
    root = root.resolve()
    org_path = org_path.resolve()
    # events.logが読めるように最低限作っておく
    (root / ".usagi").mkdir(parents=True, exist_ok=True)
    # Textual起動
    UsagiTui(root=root, org_path=org_path, model=model, offline=offline, demo=demo).run()
