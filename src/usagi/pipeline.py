"""パイプライン: 社長うさぎ → 実装うさぎ → 監査うさぎ の順で処理。"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

from usagi.agents import (
    JISSOU_USAGI,
    KANSA_USAGI,
    SHACHO_USAGI,
    AgentMessage,
    LLMBackend,
    OfflineBackend,
    OpenAIBackend,
)
from usagi.spec import UsagiSpec


class Ui(Protocol):
    def section(self, title: str) -> None: ...
    def log(self, line: str) -> None: ...
    def step(self, title: str): ...


@dataclass
class RunResult:
    report: str
    messages: list[AgentMessage] = field(default_factory=list)


def run_pipeline(
    *,
    spec: UsagiSpec,
    workdir: Path,
    model: str,
    dry_run: bool,
    offline: bool,
    ui: Ui,
) -> RunResult:
    backend: LLMBackend = OfflineBackend() if offline else OpenAIBackend()
    messages: list[AgentMessage] = []
    started = datetime.now(tz=timezone.utc).isoformat()

    ui.section(f"🐰 うさぎさん株式会社: 実行開始 / project={spec.project}")
    ui.log(f"workdir: {workdir}")
    ui.log(f"model: {model}")
    ui.log(f"dry-run: {dry_run} / offline: {offline}")

    # ── 社長うさぎ: 計画 ──
    plan_step = ui.step("🐰 社長うさぎが計画を作成中...")
    plan_prompt = _build_plan_prompt(spec)
    if dry_run:
        plan_msg = AgentMessage(agent_name="社長うさぎ", role="planner", content="(dry-run: 計画スキップ)")
    else:
        plan_msg = SHACHO_USAGI.run(user_prompt=plan_prompt, model=model, backend=backend)
    messages.append(plan_msg)
    plan_step.succeed("社長うさぎ: 計画完了")

    if dry_run:
        return RunResult(
            report=_render_report(spec=spec, workdir=workdir, started=started, messages=messages, actions=[]),
            messages=messages,
        )

    # ── 実装うさぎ: 差分生成 ──
    impl_step = ui.step("🐰 実装うさぎが生成/編集案を作成中...")
    impl_prompt = f"社長うさぎの計画:\n\n{plan_msg.content}\n\nプロジェクト名: {spec.project}"
    impl_msg = JISSOU_USAGI.run(user_prompt=impl_prompt, model=model, backend=backend)
    messages.append(impl_msg)
    impl_step.succeed("実装うさぎ: 変更案完了")

    # ── 差分適用 ──
    actions: list[str] = []
    apply_step = ui.step("変更を適用中...")
    workdir.mkdir(parents=True, exist_ok=True)
    patch_path = workdir / ".usagi.patch"
    patch_path.write_text(impl_msg.content, encoding="utf-8")
    actions.append(f"write {patch_path.name}")

    _git_init(workdir)
    try:
        subprocess.run(
            ["git", "apply", "--whitespace=nowarn", str(patch_path)],
            cwd=workdir,
            check=True,
            text=True,
            capture_output=True,
        )
        actions.append("git apply OK")
        apply_step.succeed("適用しました")
    except subprocess.CalledProcessError as e:
        actions.append(f"git apply FAILED: {e.stderr.strip()}")
        apply_step.fail("適用に失敗")

    # ── 監査うさぎ: レビュー ──
    review_step = ui.step("🐰 監査うさぎがレビュー中...")
    listing = subprocess.run(
        ["find", ".", "-not", "-path", "./.git/*", "-not", "-path", "./.git"],
        cwd=workdir,
        text=True,
        capture_output=True,
        check=False,
    ).stdout.strip()
    review_prompt = (
        f"実装うさぎが以下の差分を適用しました:\n\n{impl_msg.content}\n\n"
        f"作業ディレクトリの内容:\n```\n{listing}\n```\n\nレビューしてください。"
    )
    review_msg = KANSA_USAGI.run(user_prompt=review_prompt, model=model, backend=backend)
    messages.append(review_msg)
    actions.append("review done")
    review_step.succeed("監査うさぎ: レビュー完了")

    return RunResult(
        report=_render_report(spec=spec, workdir=workdir, started=started, messages=messages, actions=actions),
        messages=messages,
    )


def _build_plan_prompt(spec: UsagiSpec) -> str:
    tasks = "\n".join([f"- {t}" for t in spec.tasks]) if spec.tasks else "(なし)"
    constraints = "\n".join([f"- {c}" for c in spec.constraints]) if spec.constraints else "(なし)"
    return (
        f"目的:\n{spec.objective}\n\n"
        f"背景:\n{spec.context}\n\n"
        f"やること:\n{tasks}\n\n"
        f"制約:\n{constraints}\n"
    )


def _git_init(workdir: Path) -> None:
    if (workdir / ".git").exists():
        return
    subprocess.run(["git", "init"], cwd=workdir, check=True, text=True, capture_output=True)


def _render_report(
    *,
    spec: UsagiSpec,
    workdir: Path,
    started: str,
    messages: list[AgentMessage],
    actions: list[str],
) -> str:
    lines: list[str] = [
        "# 🐰 うさぎさん株式会社レポート",
        "",
        f"- 開始: {started}",
        f"- project: {spec.project}",
        f"- workdir: {workdir}",
        "",
        "## 目的",
        "",
        spec.objective or "(未記載)",
        "",
        "## 依頼内容(抽出)",
        "",
    ]
    for t in spec.tasks:
        lines.append(f"- {t}")
    if not spec.tasks:
        lines.append("(なし)")
    lines.append("")

    # エージェント会話ログ
    lines.append("## エージェント会話ログ")
    lines.append("")
    for msg in messages:
        emoji = {"planner": "👔", "coder": "💻", "reviewer": "🔍"}.get(msg.role, "🐰")
        lines.append(f"### {emoji} {msg.agent_name} ({msg.role})")
        lines.append("")
        lines.append(msg.content)
        lines.append("")

    # 実行ログ
    lines.append("## 実行ログ")
    lines.append("")
    for a in actions:
        lines.append(f"- {a}")
    if not actions:
        lines.append("(なし)")
    lines.append("")

    return "\n".join(lines) + "\n"
