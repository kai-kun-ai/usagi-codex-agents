"""指示書Markdownのバリデーション。"""

from __future__ import annotations

from dataclasses import dataclass

from usagi.spec import UsagiSpec


@dataclass
class ValidationResult:
    ok: bool
    warnings: list[str]
    errors: list[str]


def validate_spec(spec: UsagiSpec) -> ValidationResult:
    """指示書の内容を検証して問題点を返す。"""
    errors: list[str] = []
    warnings: list[str] = []

    if not spec.objective:
        errors.append("「目的」セクションが空です。")

    if not spec.tasks:
        errors.append("「やること」セクションが空です。少なくとも1つのタスクを指定してください。")

    if not spec.project or spec.project == "usagi-project":
        warnings.append(
            "project名がデフォルトのままです。"
            "frontmatterで `project: xxx` を指定すると区別しやすくなります。"
        )

    if not spec.constraints:
        warnings.append("「制約」セクションがありません。必要に応じて追加を検討してください。")

    return ValidationResult(
        ok=len(errors) == 0,
        warnings=warnings,
        errors=errors,
    )
