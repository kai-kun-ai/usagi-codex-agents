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
from textual.widgets import Button, Footer, Header, Input, ListItem, ListView, Static

from usagi.autopilot import clear_stop, request_stop, stop_requested
from usagi.boss_inbox import BossInput, write_boss_input
from usagi.demo import DemoConfig, run_demo_forever
from usagi.display import display_name
from usagi.org import load_org
from usagi.secretary import append_secretary_log, place_input_for_boss, secretary_log_path
from usagi.state import load_status
from usagi.watch import watch_inputs


def _repo_root() -> Path:
    # repo layout: <root>/src/usagi/tui.py
    return Path(__file__).resolve().parents[2]


def _discover_project_roots(root: Path) -> list[Path]:
    """org.toml探索のための候補ルート一覧。

    site-packages 配下にインストールされると __file__ からは repo を辿れないため、
    CWD や作業rootなど複数の起点から親を辿って探す。
    """

    # 優先順位: 実行root（/workなど）→ CWD → __file__由来
    bases = [root, Path.cwd(), _repo_root()]
    roots: list[Path] = []
    for b in bases:
        for p in [b, *b.parents]:
            if p in roots:
                continue
            if (p / "examples/org.toml").exists():
                roots.append(p)
                break
    return roots


def _fallback_org_path(org_path: Path, root: Path) -> Path:
    """org_path が存在しない時のフォールバック。

    典型パターン:
    - make run/demo で作業ディレクトリを /work にしている（CWD=/work）
      しかし org.toml は repo 側（/app/examples/org.toml）にある。

    そのため、org_path が見つからない場合は repo_root と root 側も探す。
    """

    if org_path.exists():
        return org_path

    project_roots = _discover_project_roots(root)

    candidates: list[Path] = []

    # まず見つかった project roots（work root / cwd / __file__ 起点）
    for pr in project_roots:
        candidates.append(pr / "examples/org.toml")
        if not org_path.is_absolute():
            candidates.append(pr / org_path)

    # 次に固定パス（docker image上のrepo）
    candidates.append(Path("/app/examples/org.toml"))

    # root/workdir側
    candidates.append(root / "examples/org.toml")
    candidates.append(Path("examples/org.toml"))

    for c in candidates:
        if c.exists():
            return c
    return org_path


def _mode_label(root: Path) -> str:
    return "STOPPED" if stop_requested(root) else "RUNNING"


def _focused_window_label(focused: object | None) -> str:
    """Return a human-friendly label for current focus.

    Textual's focus may be on a child widget (e.g. Static inside a ListItem).
    For usability we map those back to the enclosing "window" areas.
    """

    if focused is None:
        return "(none)"

    focused_id = getattr(focused, "id", None)
    if focused_id == "mode":
        return "mode"
    if focused_id == "secretary_input":
        return "秘書入力"
    if focused_id == "secretary_to_input":
        return "社長に渡す"
    if focused_id == "inputs":
        return "入力"

    # Children can have focus; try to resolve by ancestor.
    try:
        if getattr(focused, "has_ancestor")("#inputs"):
            return "入力"
    except Exception:
        pass

    try:
        if getattr(focused, "has_ancestor")("#secretary_scroll"):
            return "秘書ログ"
    except Exception:
        pass

    try:
        if getattr(focused, "has_ancestor")("#org_scroll"):
            return "組織図"
    except Exception:
        pass

    # Fall back to id or class name.
    if focused_id:
        return str(focused_id)
    return focused.__class__.__name__


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


class _InputsBox(ListView):
    """inputs一覧（選択/削除対応）。

    ListViewはキー入力を自前で消費するため、削除キーはここで拾ってAppへ委譲する。
    """

    def __init__(self, *, inputs_dir: Path, state_path: Path, max_items: int = 50, **kwargs):
        super().__init__(**kwargs)
        self.inputs_dir = inputs_dir
        self.state_path = state_path
        self.max_items = max_items
        self._paths: list[Path] = []
        # 画面のフラッシュを避けるため、同一内容なら再描画しない
        # signature: [(relative_name, done_flag)]
        self._last_signature: list[tuple[str, bool]] | None = None

    @property
    def selected_path(self) -> Path | None:
        if self.index is None:
            return None
        if self.index < 0 or self.index >= len(self._paths):
            return None
        return self._paths[self.index]

    def on_key(self, event) -> None:  # type: ignore[override]
        if event.key in {"d", "delete"}:
            try:
                self.app.action_delete_input()  # type: ignore[attr-defined]
            except Exception:
                pass
            event.stop()

    def refresh_items(self) -> None:
        inputs_dir = self.inputs_dir
        state_path = self.state_path
        inputs_dir.mkdir(parents=True, exist_ok=True)

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
        items = items[: self.max_items]

        # 既存選択を保持（再描画時にカーソルが飛ぶのを防ぐ）
        prev_selected = self.selected_path

        pending = 0
        signature: list[tuple[str, bool]] = []
        rows: list[str] = []

        if not items:
            signature = [("(no inputs)", True)]
            rows = ["(no inputs)"]
        else:
            for p, mtime_ns in items:
                last = int(state.get(str(p), 0))
                done = last >= mtime_ns
                if not done:
                    pending += 1
                try:
                    name = str(p.relative_to(inputs_dir))
                except Exception:
                    name = p.name
                signature.append((name, done))
                mark = "✅" if done else "🕒"
                rows.append(f"{mark} {name}")

        # border_titleを更新（composeで付ける前提）
        new_title = f"入力 (pending={pending})"
        if self.border_title != new_title:
            self.border_title = new_title

        # 内容が同じなら何もしない（フラッシュ/点滅防止）
        if self._last_signature == signature:
            return
        self._last_signature = signature

        # 差分更新が面倒なので、内容が変わった時だけ全置換する
        self.clear()
        self._paths = []

        if not items:
            self.append(ListItem(Static("(no inputs)")))
            self._paths = []
            return

        for (p, _mtime_ns), row in zip(items, rows, strict=False):
            self.append(ListItem(Static(row)))
            self._paths.append(p)

        # 選択を復元（同じファイルが残っている場合）
        if prev_selected is not None and prev_selected in self._paths:
            self.index = self._paths.index(prev_selected)
        elif self.index is None and self._paths:
            # 初期選択（削除キーが効くように）
            self.index = 0


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
    #focus_status { height: 3; border: solid cyan; padding: 0 1; }
    #mode { border: solid white; background: $boost; text-style: bold; }
    /* statusウィンドウは廃止（組織図へ統合） */
    #inputs { height: 12; border: solid yellow; padding: 0 1; }
    #secretary_scroll { height: 12; border: solid magenta; padding: 0 1; }
    #secretary_chat { height: auto; }

    /* NOTE:
       端末幅が狭いと Input が横幅を使い切ってボタンが画面外に押し出されるため、
       controls は縦積みにする（ボタン行を別にして常に見えるように）。
    */
    #secretary_controls { height: auto; layout: vertical; }
    #secretary_controls_buttons { height: auto; }
    #secretary_to_hint { color: $text-muted; }

    #org_scroll { height: 1fr; border: solid blue; padding: 0 1; }
    #org { height: auto; }

    #secretary_input {
        border: heavy white;
        background: $surface;
        height: 3;
        width: 1fr;
    }

    #secretary_to_input {
        background: $accent;
        color: $text;
        width: 18;
    }

    #mode:focus {
        border: heavy yellow;
        background: $boost;
    }
    """

    BINDINGS = [
        ("ctrl+s", "toggle", "Start/Stop"),
        ("ctrl+b", "secretary_to_input", "社長に渡す（ボタンと同じ）"),
        ("d", "delete_input", "Delete selected input"),
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

                    with VerticalScroll(id="secretary_scroll"):
                        chat = _SecretaryChatBox(id="secretary_chat")
                        chat.border_title = "秘書(🐻)との対話"
                        yield chat

                    with Container(id="secretary_controls"):
                        yield Input(
                            placeholder=(
                                "ここに日本語で入力 → Enter で送信"
                                "（例: 次のタスクを整理して）"
                            ),
                            id="secretary_input",
                        )
                        with Horizontal(id="secretary_controls_buttons"):
                            yield Button("社長に渡す", id="secretary_to_input")
                            yield Static("Ctrl+B", id="secretary_to_hint")

                    inputs_box = _InputsBox(
                        inputs_dir=self.root / "inputs",
                        state_path=self.root / ".usagi/state.json",
                        id="inputs",
                    )
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

            focus_status = Static("Focus: (initializing)", id="focus_status")
            focus_status.border_title = "フォーカス"
            yield focus_status
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
        # 初回描画直後に内容を埋める
        self._refresh()

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
                org_path=self.org_path,
                runtime_path=self.root / "usagi.runtime.toml",
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

        # focus indicator (bottom)
        try:
            focused = getattr(self, "focused", None)
            self.query_one("#focus_status", Static).update(
                f"Focus: {_focused_window_label(focused)}"
            )
        except Exception:
            pass

        org_path = _fallback_org_path(self.org_path, self.root)
        self.query_one(_OrgBox).update_text(
            org_path,
            self.root / ".usagi/status.json",
        )

        # 観測用: org解決先をeventsに1回だけ書く
        if not hasattr(self, "_org_path_logged"):
            self._org_path_logged = True  # type: ignore[attr-defined]
            events = self.root / ".usagi/events.log"
            events.parent.mkdir(parents=True, exist_ok=True)
            ts = time.strftime("%Y-%m-%d %H:%M:%S")
            with events.open("a", encoding="utf-8") as f:
                f.write(f"[{ts}] tui: org_path={org_path}\n")
        self.query_one(_SecretaryChatBox).update_text(self.root)
        self.query_one(_InputsBox).refresh_items()
        self.query_one(_EventsBox).update_text(self.root / ".usagi/events.log")

        # secretary autoscroll
        try:
            self.query_one("#secretary_scroll", VerticalScroll).scroll_end(animate=False)
        except Exception:
            pass

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

    def action_secretary_to_input(self) -> None:
        """秘書チャットの内容を inputs/ に起票する（ボタンと同じ）。"""
        self._secretary_to_input()

    def action_delete_input(self) -> None:
        """選択中inputを .usagi/trash/ に移動。"""
        lv = self.query_one(_InputsBox)
        p = lv.selected_path
        if p is None or not p.exists():
            return

        trash_dir = self.root / ".usagi/trash/inputs"
        trash_dir.mkdir(parents=True, exist_ok=True)
        ts = time.strftime("%Y%m%d-%H%M%S")
        dst = trash_dir / f"{ts}-{p.name}"
        try:
            p.rename(dst)
        except Exception:
            return

        events = self.root / ".usagi/events.log"
        events.parent.mkdir(parents=True, exist_ok=True)
        tss = time.strftime("%Y-%m-%d %H:%M:%S")
        with events.open("a", encoding="utf-8") as f:
            f.write(f"[{tss}] inputs: trashed {dst.name}\n")

        lv.refresh_items()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "mode":
            self.action_toggle()
        if event.button.id == "secretary_to_input":
            self._secretary_to_input()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "secretary_input":
            self._send_secretary_message()

    def on_key(self, event) -> None:  # type: ignore[override]
        # inputs一覧にフォーカスがある時だけ d/delete を削除として扱う
        if event.key not in {"d", "delete"}:
            return
        focused = getattr(self, "focused", None)
        if not focused:
            return
        if getattr(focused, "id", None) == "inputs":
            self.action_delete_input()
            event.stop()
            return
        # 子要素にフォーカスがある場合も拾う
        try:
            if focused.has_ancestor("#inputs"):
                self.action_delete_input()
                event.stop()
        except Exception:
            return

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
    # org_path は CWD に依存して resolve されると /work/examples/... のようにズレるため、
    # ここでは解決しない（TUI側のフォールバック探索に任せる）。
    # events.logが読めるように最低限作っておく
    (root / ".usagi").mkdir(parents=True, exist_ok=True)
    # Textual起動
    UsagiTui(root=root, org_path=org_path, model=model, offline=offline, demo=demo).run()
