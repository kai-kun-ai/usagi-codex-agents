"""ワーカーコンテナ管理。

各ワーカーをDockerコンテナとして起動し、
git worktree で個別の作業環境を提供する。

フロー:
1. worker が task を受け取る
2. git worktree add で worker 専用ブランチを作成
3. Docker コンテナを起動（worktree をマウント、profile の codex_config を注入）
4. コンテナ内で codex exec 実行
5. 結果を課(lead)ブランチにマージ要求
6. 課長(lead)が承認→課ブランチにマージ
7. 部長(manager)が課ブランチを main にマージして良いか判断
8. main へのマージ自体は社長(boss)権限（運用ポリシーとして強制予定）
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from usagi.org import ROLE_BOSS, ROLE_LEAD, ROLE_MANAGER, AgentDef, Organization

try:
    # profiles.py が導入済みの場合はそれを使う
    from usagi.profiles import ProfileDef  # type: ignore
except Exception:  # pragma: no cover
    # まだ profiles が無い環境でも動くように最小定義を持つ
    @dataclass
    class ProfileDef:  # type: ignore[no-redef]
        name: str
        codex_config: str = ""
        docker_image: str = "usagi-worker:latest"
        env: dict[str, str] = None  # type: ignore[assignment]



@dataclass
class WorkerBranch:
    """ワーカーの作業ブランチ情報。"""

    worker_id: str
    branch_name: str
    worktree_path: Path
    team_branch: str  # 課(lead)のブランチ


@dataclass
class BranchPolicy:
    """ブランチマージ権限ポリシー。"""

    org: Organization

    def can_merge_to_team(self, agent_id: str, team_branch: str) -> bool:
        """課ブランチへのマージ権限（課長以上）。"""
        agent = self.org.find(agent_id)
        if not agent:
            return False
        return agent.role in (ROLE_LEAD, ROLE_MANAGER, ROLE_BOSS)

    def can_merge_to_main(self, agent_id: str) -> bool:
        """mainブランチへのマージ権限（社長のみ）。"""
        agent = self.org.find(agent_id)
        if not agent:
            return False
        return agent.role == ROLE_BOSS

    def needs_escalation(self, agent_id: str, is_critical: bool = False) -> bool:
        """社長判断が必要か（クリティカル案件時）。"""
        if not is_critical:
            return False
        agent = self.org.find(agent_id)
        if not agent:
            return True
        return agent.role != ROLE_BOSS


def create_worktree(
    repo_root: Path,
    worker: AgentDef,
    task_id: str,
    team_branch: str,
) -> WorkerBranch:
    """ワーカー用の git worktree を作成。"""
    branch_name = f"worker/{worker.id}/{task_id}"
    worktree_path = repo_root / ".worktrees" / worker.id / task_id

    # team branch が無ければ作成
    _ensure_branch(repo_root, team_branch)

    # worktree 作成（team_branch から派生）
    subprocess.run(
        [
            "git",
            "worktree",
            "add",
            "-b",
            branch_name,
            str(worktree_path),
            team_branch,
        ],
        cwd=repo_root,
        check=True,
        capture_output=True,
    )

    return WorkerBranch(
        worker_id=worker.id,
        branch_name=branch_name,
        worktree_path=worktree_path,
        team_branch=team_branch,
    )


def remove_worktree(repo_root: Path, wb: WorkerBranch) -> None:
    """worktree を削除。"""
    subprocess.run(
        ["git", "worktree", "remove", str(wb.worktree_path), "--force"],
        cwd=repo_root,
        check=False,
        capture_output=True,
    )
    # ブランチも削除
    subprocess.run(
        ["git", "branch", "-D", wb.branch_name],
        cwd=repo_root,
        check=False,
        capture_output=True,
    )


def _ensure_branch(repo_root: Path, branch: str) -> None:
    """ブランチが存在しなければ HEAD から作成。"""
    r = subprocess.run(
        ["git", "rev-parse", "--verify", branch],
        cwd=repo_root,
        capture_output=True,
    )
    if r.returncode != 0:
        subprocess.run(
            ["git", "branch", branch],
            cwd=repo_root,
            check=True,
            capture_output=True,
        )


def build_container_run_cmd(
    worker: AgentDef,
    wb: WorkerBranch,
    profile: ProfileDef | None,
    task_file: Path,
) -> list[str]:
    """ワーカーコンテナ起動用の docker run コマンドを構築。"""
    image = "usagi-worker:latest"
    env_args: list[str] = []

    if profile:
        image = getattr(profile, "docker_image", "") or image
        codex_config = getattr(profile, "codex_config", "")
        if codex_config:
            env_args.extend([
                "-v",
                f"{codex_config}:/home/worker/.codex/config.toml:ro",
            ])
        extra_env = getattr(profile, "env", None) or {}
        for k, v in extra_env.items():
            env_args.extend(["-e", f"{k}={v}"])

    cmd = [
        "docker",
        "run",
        "--rm",
        "-v",
        f"{wb.worktree_path}:/work",
        "-v",
        f"{task_file}:/task.md:ro",
        "-w",
        "/work",
        *env_args,
        image,
        "codex",
        "exec",
        "--file",
        "/task.md",
    ]
    return cmd
