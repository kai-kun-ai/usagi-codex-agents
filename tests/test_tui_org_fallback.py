from pathlib import Path

from usagi import tui


def test_fallback_org_path_prefers_existing(tmp_path: Path) -> None:
    org = tmp_path / "org.toml"
    org.write_text("x", encoding="utf-8")
    assert tui._fallback_org_path(org, tmp_path) == org


def test_fallback_org_path_prefers_repo_root(monkeypatch, tmp_path: Path) -> None:
    # repo_root/examples/org.toml が見つかるならそれを返す
    repo_root = tmp_path / "repo"
    (repo_root / "examples").mkdir(parents=True)
    ex = repo_root / "examples/org.toml"
    ex.write_text("x", encoding="utf-8")

    monkeypatch.setattr(tui, "_repo_root", lambda: repo_root)

    missing = tmp_path / "missing.toml"
    resolved = tui._fallback_org_path(missing, tmp_path)
    assert resolved == ex
