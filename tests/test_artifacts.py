"""artifacts のテスト。"""

from pathlib import Path

from usagi.artifacts import artifacts_dir, write_artifact


def test_write_artifact_creates_dir(tmp_path: Path) -> None:
    workdir = tmp_path / "work"
    p = write_artifact(workdir, "10-boss-plan.md", "hello")
    assert p.exists()
    assert p.read_text(encoding="utf-8") == "hello"
    assert artifacts_dir(workdir).exists()
