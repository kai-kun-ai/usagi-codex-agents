"""pipeline のオフラインモードテスト。"""

from pathlib import Path

from usagi.pipeline import run_pipeline
from usagi.spec import UsagiSpec


class DummyStep:
    def succeed(self, _message: str | None = None) -> None:
        return None

    def fail(self, _message: str | None = None) -> None:
        return None


class DummyUi:
    def section(self, _title: str) -> None:
        return None

    def log(self, _line: str) -> None:
        return None

    def step(self, _title: str) -> DummyStep:
        return DummyStep()


def test_offline_pipeline_creates_report(tmp_path: Path) -> None:
    spec = UsagiSpec(
        project="test-proj",
        objective="テスト",
        context="",
        tasks=["README.md を生成"],
        constraints=[],
    )
    result = run_pipeline(
        spec=spec,
        workdir=tmp_path,
        model="codex",
        dry_run=False,
        offline=True,
        ui=DummyUi(),
    )
    assert "# 🐰 うさぎさん株式会社レポート" in result.report
    assert "test-proj" in result.report
    assert len(result.messages) == 3  # planner + coder + reviewer


def test_dry_run_skips_execution(tmp_path: Path) -> None:
    spec = UsagiSpec(project="dry", objective="テスト", tasks=["何かする"])
    result = run_pipeline(
        spec=spec,
        workdir=tmp_path,
        model="codex",
        dry_run=True,
        offline=True,
        ui=DummyUi(),
    )
    assert "dry" in result.report
    assert len(result.messages) == 1  # planner only
