"""ワーカーコンテナ管理テスト。"""

from pathlib import Path

from usagi.org import AgentDef, Organization, ROLE_BOSS, ROLE_MANAGER, ROLE_WORKER
from usagi.profiles import ProfileDef
from usagi.worker_container import BranchPolicy, build_container_run_cmd, WorkerBranch


def test_branch_policy_merge_to_team() -> None:
    org = Organization(
        agents=[
            AgentDef(id="boss", name="B", role=ROLE_BOSS),
            AgentDef(id="mgr", name="M", role=ROLE_MANAGER, reports_to="boss"),
            AgentDef(id="w1", name="W", role=ROLE_WORKER, reports_to="mgr"),
        ]
    )
    policy = BranchPolicy(org=org)
    assert policy.can_merge_to_team("mgr", "team/dev")
    assert policy.can_merge_to_team("boss", "team/dev")
    assert not policy.can_merge_to_team("w1", "team/dev")


def test_branch_policy_merge_to_main() -> None:
    org = Organization(
        agents=[
            AgentDef(id="boss", name="B", role=ROLE_BOSS),
            AgentDef(id="mgr", name="M", role=ROLE_MANAGER, reports_to="boss"),
        ]
    )
    policy = BranchPolicy(org=org)
    assert policy.can_merge_to_main("boss")
    assert not policy.can_merge_to_main("mgr")


def test_needs_escalation() -> None:
    org = Organization(
        agents=[
            AgentDef(id="boss", name="B", role=ROLE_BOSS),
            AgentDef(id="mgr", name="M", role=ROLE_MANAGER, reports_to="boss"),
        ]
    )
    policy = BranchPolicy(org=org)
    assert not policy.needs_escalation("mgr", is_critical=False)
    assert policy.needs_escalation("mgr", is_critical=True)
    assert not policy.needs_escalation("boss", is_critical=True)


def test_build_container_run_cmd(tmp_path: Path) -> None:
    worker = AgentDef(id="w1", name="W", role=ROLE_WORKER, profile="acct_a")
    wb = WorkerBranch(
        worker_id="w1",
        branch_name="worker/w1/task1",
        worktree_path=tmp_path / "wt",
        team_branch="team/dev",
    )
    profile = ProfileDef(
        name="acct_a",
        codex_config="/tmp/codex_a.toml",
        docker_image="myimg:latest",
        env={"FOO": "bar"},
    )
    task = tmp_path / "task.md"
    task.write_text("# task", encoding="utf-8")

    cmd = build_container_run_cmd(worker, wb, profile, task)
    assert "docker" in cmd[0]
    assert "myimg:latest" in cmd
    assert "-e" in cmd
    assert "FOO=bar" in cmd
    assert "/tmp/codex_a.toml:/home/worker/.codex/config.toml:ro" in cmd


def test_build_container_run_cmd_no_profile(tmp_path: Path) -> None:
    worker = AgentDef(id="w1", name="W", role=ROLE_WORKER)
    wb = WorkerBranch(
        worker_id="w1",
        branch_name="worker/w1/task1",
        worktree_path=tmp_path / "wt",
        team_branch="team/dev",
    )
    task = tmp_path / "task.md"
    task.write_text("# task", encoding="utf-8")

    cmd = build_container_run_cmd(worker, wb, None, task)
    assert "usagi-worker:latest" in cmd
