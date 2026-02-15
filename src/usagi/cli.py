"""usagi CLI エントリポイント。"""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from usagi.autopilot import clear_stop, request_stop
from usagi.boss_inbox import BossInput, write_boss_input
from usagi.pipeline import run_pipeline
from usagi.spec import parse_spec_markdown
from usagi.state import load_status
from usagi.tui import run_tui
from usagi.validate import validate_spec
from usagi.watch import watch_inputs

APP_HELP = "🐰 うさぎさん株式会社: Markdown指示で動くCodex向けマルチエージェントCLI"

app = typer.Typer(add_completion=False, help=APP_HELP)
console = Console()


class _Step:
    """Rich spinnerを模したシンプルなステップUI。"""

    def __init__(self, title: str) -> None:
        console.print(f"  ⏳ {title}", style="dim")

    def succeed(self, message: str | None = None) -> None:
        console.print(f"  ✅ {message or 'OK'}", style="green")

    def fail(self, message: str | None = None) -> None:
        console.print(f"  ❌ {message or 'FAILED'}", style="red")


class RichUi:
    def section(self, title: str) -> None:
        console.print(f"\n{'=' * 60}", style="cyan")
        console.print(f"  {title}", style="bold cyan")
        console.print(f"{'=' * 60}\n", style="cyan")

    def log(self, line: str) -> None:
        console.print(f"  {line}", style="dim")

    def step(self, title: str) -> _Step:
        return _Step(title)


@app.command()
def run(
    spec: Path = typer.Argument(
        ...,
        help="指示書Markdownへのパス (例: specs/sample.md)",
    ),
    out: Path | None = typer.Option(
        None, "--out", help="出力レポートMarkdownのパス"
    ),
    workdir: Path = typer.Option(
        Path("."), "--workdir", help="作業ディレクトリ"
    ),
    model: str = typer.Option(
        "codex", "--model", help="利用モデル (例: codex / gpt-4.1)"
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="実行せずに計画だけ出す"
    ),
    offline: bool = typer.Option(
        False, "--offline", help="APIを呼ばずにダミーで動作確認"
    ),
) -> None:
    """Markdown指示書→マルチエージェント実行→レポート出力。"""
    if not spec.exists():
        console.print(f"❌ 指示書が見つかりません: {spec}", style="red")
        raise typer.Exit(code=1)

    md = spec.read_text(encoding="utf-8")
    usagi_spec = parse_spec_markdown(md)

    result = run_pipeline(
        spec=usagi_spec,
        workdir=workdir.resolve(),
        model=model,
        dry_run=dry_run,
        offline=offline,
        ui=RichUi(),
    )

    if out is not None:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(result.report, encoding="utf-8")
        console.print(
            f"\n🐰 レポートを書き出しました: {out.resolve()}",
            style="bold green",
        )
    else:
        console.print()
        console.print(result.report)


@app.command()
def watch(
    inputs: Path = typer.Option(Path("inputs"), "--inputs", help="監視する入力フォルダ"),
    outputs: Path = typer.Option(Path("outputs"), "--outputs", help="レポート出力フォルダ"),
    work_root: Path = typer.Option(Path("work"), "--work-root", help="作業フォルダ"),
    state: Path = typer.Option(Path(".usagi/state.json"), "--state", help="処理済み状態ファイル"),
    debounce: float = typer.Option(0.25, "--debounce", help="デバウンス秒"),
    recursive: bool = typer.Option(True, "--recursive/--no-recursive", help="サブフォルダも監視"),
    model: str = typer.Option("codex", "--model", help="利用モデル"),
    dry_run: bool = typer.Option(False, "--dry-run", help="実行せずに計画だけ"),
    offline: bool = typer.Option(False, "--offline", help="APIを呼ばずにダミーで動作確認"),
) -> None:
    """inputsフォルダを監視して指示書を自動処理する。"""
    console.print(f"watching: {inputs} -> {outputs}", style="cyan")
    watch_inputs(
        inputs_dir=inputs,
        outputs_dir=outputs,
        work_root=work_root,
        state_path=state,
        debounce_seconds=debounce,
        model=model,
        dry_run=dry_run,
        offline=offline,
        recursive=recursive,
        stop_file=Path(".usagi/STOP"),
        status_path=Path(".usagi/status.json"),
        event_log_path=Path(".usagi/events.log"),
    )


@app.command()
def autopilot_start(
    inputs: Path = typer.Option(Path("inputs"), "--inputs", help="入力フォルダ"),
    outputs: Path = typer.Option(Path("outputs"), "--outputs", help="出力フォルダ"),
    work_root: Path = typer.Option(Path("work"), "--work-root", help="作業フォルダ"),
    state: Path = typer.Option(Path(".usagi/state.json"), "--state", help="状態ファイル"),
    model: str = typer.Option("codex", "--model", help="利用モデル"),
    offline: bool = typer.Option(False, "--offline", help="APIを呼ばずに動作確認"),
) -> None:
    """autopilot start（watchを止めるまで走らせる）。"""
    clear_stop(Path("."))
    console.print("autopilot start -> watch", style="cyan")

    watch_inputs(
        inputs_dir=inputs,
        outputs_dir=outputs,
        work_root=work_root,
        state_path=state,
        debounce_seconds=0.25,
        model=model,
        dry_run=False,
        offline=offline,
        recursive=True,
        stop_file=Path(".usagi/STOP"),
        status_path=Path(".usagi/status.json"),
        event_log_path=Path(".usagi/events.log"),
    )


@app.command()
def autopilot_stop() -> None:
    """autopilot stop（停止要求を出す）。"""
    p = request_stop(Path("."))
    console.print(f"stop requested: {p}", style="yellow")


@app.command()
def status(
    status_path: Path = typer.Option(Path(".usagi/status.json"), "--status", help="状態ファイル"),
) -> None:
    """稼働中/待機中のうさぎを表示する。"""
    st = load_status(status_path)
    if not st.agents:
        console.print("(no status)")
        return

    for a in st.agents.values():
        console.print(f"- {a.name} ({a.agent_id}): {a.state} {a.task}")


@app.command()
def input(
    text: str = typer.Option("", "--text", help="投入するテキスト（空なら対話）"),
) -> None:
    """boss input を投入（チャット入力）。"""
    if not text:
        console.print("入力してください（空行で終了）:")
        lines = []
        while True:
            line = typer.prompt("", default="", show_default=False)
            if not line:
                break
            lines.append(line)
        text = "\n".join(lines).strip()

    if not text:
        return

    p = write_boss_input(Path("."), BossInput(source="cli", text=text))
    console.print(f"saved: {p}", style="green")


@app.command()
def mcp() -> None:
    """stdin MCP wrapper を起動（簡易）。"""
    from usagi.mcp_stdin import StdinMCP, Tool

    tools = [Tool(name="echo", description="echo text", schema={"type": "object"})]
    StdinMCP(tools).run()


@app.command()
def tui(
    root: Path = typer.Option(
        Path("."),
        "--root",
        help="作業ルート（inputs/outputs/.usagi が置かれる場所）",
    ),
    model: str = typer.Option("codex", "--model", help="利用モデル"),
    offline: bool = typer.Option(False, "--offline", help="APIを呼ばずにダミーで動作確認"),
    demo: bool = typer.Option(False, "--demo", help="デモ（疑似稼働）モード"),
) -> None:
    """統合CUI（管理画面）を起動。"""
    run_tui(root=root, model=model, offline=offline, demo=demo)


@app.command()
def validate(
    spec: Path = typer.Argument(
        ...,
        help="検証する指示書Markdownへのパス",
    ),
) -> None:
    """指示書Markdownの内容を検証して問題点を表示。"""
    if not spec.exists():
        console.print(f"❌ ファイルが見つかりません: {spec}", style="red")
        raise typer.Exit(code=1)

    md = spec.read_text(encoding="utf-8")
    usagi_spec = parse_spec_markdown(md)
    result = validate_spec(usagi_spec)

    if result.errors:
        for e in result.errors:
            console.print(f"  ❌ {e}", style="red")
    if result.warnings:
        for w in result.warnings:
            console.print(f"  ⚠️  {w}", style="yellow")
    if result.ok:
        console.print("  ✅ 指示書に問題はありません。", style="green")
    else:
        raise typer.Exit(code=1)
