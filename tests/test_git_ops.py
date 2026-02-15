"""git_ops のテスト（gitは実行できる前提）。"""

from pathlib import Path

import pytest

from usagi.git_ops import GitRepo, org_branch, team_branch


def test_org_branch() -> None:
    assert org_branch("dev") == "org/dev"


def test_team_branch() -> None:
    assert team_branch("dev_lead") == "team-dev_lead"


def test_git_repo_init_and_branch(tmp_path: Path) -> None:
    repo = GitRepo(tmp_path)
    repo.ensure_repo()

    # commit requires identity, so skip if missing
    try:
        repo.run(["config", "user.name"])
        repo.run(["config", "user.email"])
    except RuntimeError:
        pytest.skip("git identity not configured")

    (tmp_path / "a.txt").write_text("hi", encoding="utf-8")
    repo.add_all()
    repo.commit("init")

    b = org_branch("worker1")
    repo.checkout(b, create=True)
    assert repo.current_branch() == b
