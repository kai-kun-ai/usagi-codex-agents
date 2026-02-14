"""usagi CLI エントリポイント。"""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from usagi.pipeline import run_pipeline
from usagi.spec import parse_spec_markdown
from usagi.validate import validate_spec

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
