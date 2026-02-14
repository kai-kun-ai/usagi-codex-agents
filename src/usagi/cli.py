from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from usagi.pipeline import run_pipeline
from usagi.spec import parse_spec_markdown

app = typer.Typer(add_completion=False)
console = Console()


class Step:
    def __init__(self, progress: Progress, task_id: int) -> None:
        self._progress = progress
        self._task_id = task_id

    def succeed(self, message: str | None = None) -> None:
        self._progress.update(self._task_id, description=(message or "OK"))
        self._progress.stop_task(self._task_id)

    def fail(self, message: str | None = None) -> None:
        self._progress.update(self._task_id, description=(message or "FAILED"))
        self._progress.stop_task(self._task_id)


class RichUi:
    def section(self, title: str) -> None:
        console.print(f"\n== {title}\n", style="bold cyan")

    def log(self, line: str) -> None:
        console.print(line)

    def step(self, title: str) -> Step:
        progress = Progress(SpinnerColumn(), TextColumn("{task.description}"), transient=True)
        progress.start()
        task_id = progress.add_task(title)
        return Step(progress, task_id)


@app.command()
def run(
    spec: Path = typer.Argument(..., help="指示書Markdownへのパス (例: specs/todo.md)"),
    out: Path | None = typer.Option(None, "--out", help="出力レポートMarkdownのパス"),
    workdir: Path = typer.Option(Path("."), "--workdir", help="作業ディレクトリ"),
    model: str = typer.Option("codex", "--model", help="利用モデル (例: codex / gpt-4.1 / gpt-5.2 など)"),
    dry_run: bool = typer.Option(False, "--dry-run", help="実行せずに計画だけ出す"),
    offline: bool = typer.Option(False, "--offline", help="OpenAI APIを呼ばずにオフラインのダミー出力で動作確認する"),
) -> None:
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
        console.print(f"\nレポートを書き出しました: {out.resolve()}", style="green")
    else:
        console.print("\n" + result.report)
