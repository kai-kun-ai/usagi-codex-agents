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


def test_run_pipeline_offline_creates_readme(tmp_path: Path) -> None:
    spec = UsagiSpec(project="demo", objective="", context="", tasks=["README.md を生成"], constraints=[])
    res = run_pipeline(spec=spec, workdir=tmp_path, model="codex", dry_run=False, offline=True, ui=DummyUi())
    assert (tmp_path / "README.md").exists()
    assert "# うさぎさん株式会社レポート" in res.report
