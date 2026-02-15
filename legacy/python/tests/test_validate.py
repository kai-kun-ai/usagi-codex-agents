"""validate モジュールのテスト。"""

from usagi.spec import UsagiSpec
from usagi.validate import validate_spec


def test_valid_spec() -> None:
    spec = UsagiSpec(
        project="demo",
        objective="テスト",
        tasks=["task1"],
        constraints=["制約1"],
    )
    result = validate_spec(spec)
    assert result.ok is True
    assert result.errors == []
    assert result.warnings == []


def test_missing_objective() -> None:
    spec = UsagiSpec(project="demo", objective="", tasks=["task1"])
    result = validate_spec(spec)
    assert result.ok is False
    assert any("目的" in e for e in result.errors)


def test_missing_tasks() -> None:
    spec = UsagiSpec(project="demo", objective="テスト", tasks=[])
    result = validate_spec(spec)
    assert result.ok is False
    assert any("やること" in e for e in result.errors)


def test_default_project_warning() -> None:
    spec = UsagiSpec(objective="テスト", tasks=["task1"])
    result = validate_spec(spec)
    assert result.ok is True
    assert any("project" in w for w in result.warnings)


def test_no_constraints_warning() -> None:
    spec = UsagiSpec(project="demo", objective="テスト", tasks=["task1"])
    result = validate_spec(spec)
    assert result.ok is True
    assert any("制約" in w for w in result.warnings)
