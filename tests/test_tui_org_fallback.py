from pathlib import Path

from usagi import tui


def test_fallback_org_path_prefers_existing(tmp_path: Path) -> None:
    org = tmp_path / "org.toml"
    org.write_text("x", encoding="utf-8")
    assert tui._fallback_org_path(org, tmp_path) == org


def test_discover_project_roots_finds_examples(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    (repo_root / "examples").mkdir(parents=True)
    (repo_root / "examples/org.toml").write_text("x", encoding="utf-8")

    roots = tui._discover_project_roots(repo_root)
    assert repo_root in roots


def test_fallback_org_path_prefers_project_root(monkeypatch, tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    (repo_root / "examples").mkdir(parents=True)
    ex = repo_root / "examples/org.toml"
    ex.write_text("x", encoding="utf-8")

    # __file__ 由来のrepo_rootが外れても、探索で拾えること
    monkeypatch.setattr(tui, "_repo_root", lambda: tmp_path / "site-packages")

    resolved = tui._fallback_org_path(Path("examples/org.toml"), repo_root)
    assert resolved == ex
