"""レポート生成モジュール。エージェントの会話ログをMarkdownに整形。"""

from __future__ import annotations

from pathlib import Path

from usagi.agents import AgentMessage
from usagi.spec import UsagiSpec

ROLE_EMOJI = {
    "planner": "👔",
    "coder": "💻",
    "reviewer": "🔍",
}


def render_report(
    *,
    spec: UsagiSpec,
    workdir: Path,
    started: str,
    messages: list[AgentMessage],
    actions: list[str],
    round_num: int = 1,
) -> str:
    lines: list[str] = [
        "# 🐰 うさぎさん株式会社レポート",
        "",
        f"- 開始: {started}",
        f"- project: {spec.project}",
        f"- workdir: `{workdir}`",
        f"- ラウンド数: {round_num}",
        "",
        "---",
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

    if spec.constraints:
        lines.append("## 制約")
        lines.append("")
        for c in spec.constraints:
            lines.append(f"- {c}")
        lines.append("")

    # エージェント会話ログ
    lines.append("---")
    lines.append("")
    lines.append("## エージェント会話ログ")
    lines.append("")

    current_round = 0
    for msg in messages:
        if msg.role == "planner":
            current_round += 1
            if round_num > 1:
                lines.append(f"### ラウンド {current_round}")
                lines.append("")

        emoji = ROLE_EMOJI.get(msg.role, "🐰")
        lines.append(f"#### {emoji} {msg.agent_name} ({msg.role})")
        lines.append("")
        lines.append(msg.content)
        lines.append("")

    # 実行ログ
    lines.append("---")
    lines.append("")
    lines.append("## 実行ログ")
    lines.append("")
    for a in actions:
        lines.append(f"- {a}")
    if not actions:
        lines.append("(なし)")
    lines.append("")

    return "\n".join(lines) + "\n"
