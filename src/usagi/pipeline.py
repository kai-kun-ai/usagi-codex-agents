from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess
from typing import Protocol

from openai import OpenAI

from usagi.spec import UsagiSpec


class Ui(Protocol):
    def section(self, title: str) -> None: ...

    def log(self, line: str) -> None: ...

    def step(self, title: str): ...


@dataclass
class RunResult:
    report: str


def run_pipeline(*, spec: UsagiSpec, workdir: Path, model: str, dry_run: bool, offline: bool, ui: Ui) -> RunResult:
    ui.section(f"うさぎさん株式会社: 実行開始 / project={spec.project}")
    ui.log(f"workdir: {workdir}")
    ui.log(f"model: {model}")
    ui.log(f"dry-run: {dry_run}")
    ui.log(f"offline: {offline}")

    plan_step = ui.step("社長うさぎが計画を作成中...")
    plan = make_plan_offline(spec) if (offline or dry_run) else make_plan(spec, model=model)
    plan_step.succeed("計画ができました")

    if dry_run:
        return RunResult(
            report=render_report(
                spec=spec,
                workdir=workdir,
                plan=plan,
                actions=[],
                notes=["dry-runのため実行はしていません（offline計画）"],
            )
        )

    workdir.mkdir(parents=True, exist_ok=True)

    impl_step = ui.step("実装うさぎが生成/編集案を作成中...")
    patch = make_patch_offline(spec) if offline else make_patch(spec, plan=plan, model=model)
    impl_step.succeed("変更案ができました")

    apply_step = ui.step("変更を適用中...")
    actions: list[str] = []
    patch_path = workdir / ".usagi.patch"
    patch_path.write_text(patch, encoding="utf-8")
    actions.append(f"write {patch_path}")

    _git_init(workdir)
    try:
        subprocess.run(
            ["git", "apply", "--whitespace=nowarn", str(patch_path)],
            cwd=workdir,
            check=True,
            text=True,
            capture_output=True,
        )
        actions.append("git apply .usagi.patch")
        apply_step.succeed("適用しました")
    except subprocess.CalledProcessError as e:
        apply_step.fail("適用に失敗")
        actions.append(f"patch apply failed: {e.stderr.strip()}")

    chk_step = ui.step("監査うさぎが簡易チェック中...")
    listing = subprocess.run(
        ["bash", "-lc", "ls -la"],
        cwd=workdir,
        check=True,
        text=True,
        capture_output=True,
    ).stdout
    actions.append("ls -la")
    chk_step.succeed("チェック完了")

    return RunResult(
        report=render_report(
            spec=spec,
            workdir=workdir,
            plan=plan,
            actions=actions,
            notes=["作業ディレクトリの一覧:\n\n```\n" + listing + "\n```"],
        )
    )


def _git_init(workdir: Path) -> None:
    if (workdir / ".git").exists():
        return
    subprocess.run(["git", "init"], cwd=workdir, check=True, text=True, capture_output=True)


def make_plan_offline(spec: UsagiSpec) -> str:
    steps = "\n".join([f"{i + 1}. {t}" for i, t in enumerate(spec.tasks)]) if spec.tasks else "1. READMEを作成"
    return (
        "## 方針\n\n"
        "- まずは最小の成果物を作り、動くことを確認してから拡張します。\n\n"
        "## 作業ステップ\n\n"
        f"{steps}\n\n"
        "## リスク\n\n"
        "- OpenAI APIキー未設定/権限不足\n"
        "- unified diff が適用できない差分が生成される可能性\n\n"
        "## 完了条件\n\n"
        "- 指示されたファイルが作成され、簡易チェックが通ること\n"
    )


def make_plan(spec: UsagiSpec, *, model: str) -> str:
    client = OpenAI()
    prompt = (
        "あなたは『うさぎさん株式会社』の社長うさぎです。\n\n"
        f"目的:\n{spec.objective}\n\n"
        f"背景:\n{spec.context}\n\n"
        "やること(箇条書き):\n" + "\n".join([f"- {t}" for t in spec.tasks]) + "\n\n"
        "制約:\n" + "\n".join([f"- {c}" for c in spec.constraints]) + "\n\n"
        "出力: 実行計画をMarkdownで。セクション: 方針 / 作業ステップ / リスク / 完了条件。"
    )
    resp = client.responses.create(model=model, input=prompt)
    return resp.output_text or ""


def make_patch_offline(spec: UsagiSpec) -> str:
    project = spec.project
    readme = f"# {project}\n\nこれは『うさぎさん株式会社(usagi)』のオフラインモードで生成されたサンプルです。\n"
    readme_lines = "\n".join(["+" + line for line in readme.splitlines()]) + "\n"
    return (
        "diff --git a/README.md b/README.md\n"
        "new file mode 100644\n"
        "index 0000000..1111111\n"
        "--- /dev/null\n"
        "+++ b/README.md\n"
        "@@ -0,0 +1,3 @@\n"
        + readme_lines
    )


def make_patch(spec: UsagiSpec, *, plan: str, model: str) -> str:
    client = OpenAI()
    prompt = (
        "あなたは『うさぎさん株式会社』の実装うさぎです。\n\n"
        "次の計画に沿って、最小構成の成果物を作ってください。\n\n"
        f"計画:\n{plan}\n\n"
        "要件:\n"
        "- 変更は 'Unified diff' 形式で出力してください（git diffと同様）。\n"
        "- ルートに README.md を必ず作る。\n"
        "- 可能なら動くサンプル(簡単なCLIやスクリプト)も含める。\n"
        "- 文章は日本語。\n\n"
        f"プロジェクト名: {spec.project}\n"
    )
    resp = client.responses.create(model=model, input=prompt)
    return resp.output_text or ""


def render_report(*, spec: UsagiSpec, workdir: Path, plan: str, actions: list[str], notes: list[str]) -> str:
    return (
        "# うさぎさん株式会社レポート\n\n"
        f"- project: {spec.project}\n"
        f"- workdir: {workdir}\n\n"
        "## 目的\n\n"
        f"{spec.objective or '(未記載)'}\n\n"
        "## 依頼内容(抽出)\n\n"
        + ("\n".join([f"- {t}" for t in spec.tasks]) if spec.tasks else "(なし)")
        + "\n\n"
        "## 社長うさぎの計画\n\n"
        + (plan or "(空)")
        + "\n\n"
        "## 実行ログ\n\n"
        + ("\n".join([f"- {a}" for a in actions]) if actions else "(なし)")
        + "\n\n"
        "## メモ\n\n"
        + "\n\n".join(notes)
        + "\n"
    )
