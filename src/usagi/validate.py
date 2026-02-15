"""指示書Markdownのバリデーション。

フォーマットが不足していても AI で咀嚼する方針。
strict=True にすると従来通りエラーにする（テスト用）。
"""

from __future__ import annotations

from dataclasses import dataclass

from usagi.spec import UsagiSpec


@dataclass
class ValidationResult:
    ok: bool
    warnings: list[str]
    errors: list[str]


def validate_spec(spec: UsagiSpec, *, strict: bool = False) -> ValidationResult:
    """指示書の内容を検証して問題点を返す。

    strict=False（デフォルト）: 不足項目は warnings に格下げし ok=True を返す。
    strict=True: 従来通り errors にして ok=False にする。
    """
    errors: list[str] = []
    warnings: list[str] = []

    if not spec.objective:
        msg = "「目的」セクションが空です。"
        if strict:
            errors.append(msg)
        else:
            warnings.append(msg + "AIが内容から推測します。")

    if not spec.tasks:
        msg = "「やること」セクションが空です。"
        if strict:
            errors.append(msg + "少なくとも1つのタスクを指定してください。")
        else:
            warnings.append(msg + "AIが内容から推測します。")

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
