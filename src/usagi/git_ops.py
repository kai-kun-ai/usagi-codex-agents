"""git 操作ユーティリティ。

方針:
- 組織(agents)ごとに作業ブランチを分ける（org/dev_mgr など）
- worker/manager は自分のブランチでコミットまで
- merge/PR merge は boss のみ（運用ポリシーとして runtime 側で制御）

このモジュールはローカルgit操作のみ提供。
GitHub操作は gh_enabled が true のときだけ別モジュールで扱う。
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class GitRepo:
    path: Path

    def run(self, args: list[str]) -> str:
        proc = subprocess.run(
            ["git", *args],
            cwd=self.path,
            text=True,
            capture_output=True,
            check=False,
        )
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr.strip() or "git failed")
        return proc.stdout.strip()

    def ensure_repo(self) -> None:
        if (self.path / ".git").exists():
            return
        # default branch を main に揃える
        self.run(["init", "-b", "main"])

    def ensure_user(self) -> None:
        # 署名不要。ローカル専用。
        try:
            self.run(["config", "user.email"])
        except Exception:
            self.run(["config", "user.email", "usagi@example.invalid"])
        try:
            self.run(["config", "user.name"])
        except Exception:
            self.run(["config", "user.name", "usagi"])

    def ensure_initial_commit(self) -> None:
        """ブランチ作成/merge のため最低1コミットを保証する。"""

        self.ensure_user()
        proc = subprocess.run(
            ["git", "rev-parse", "--verify", "HEAD"],
            cwd=self.path,
            text=True,
            capture_output=True,
        )
        if proc.returncode == 0:
            return
        self.run(["commit", "--allow-empty", "-m", "init"])

    def worktree_add(self, worktree_path: Path, branch: str) -> None:
        worktree_path.parent.mkdir(parents=True, exist_ok=True)
        if worktree_path.exists():
            return
        # branch が無いなら main から作る
        if not self.branch_exists(branch):
            self.run(["branch", branch, "main"])
        self.run(["worktree", "add", str(worktree_path), branch])

    def worktree_remove(self, worktree_path: Path) -> None:
        if not worktree_path.exists():
            return
        self.run(["worktree", "remove", "--force", str(worktree_path)])

    def merge_to_main_and_delete_branch(self, branch: str) -> None:
        """main に merge し、作業ブランチを削除する。"""

        self.ensure_user()
        self.checkout("main")
        self.run(["merge", "--no-edit", branch])
        self.run(["branch", "-D", branch])

    def current_branch(self) -> str:
        return self.run(["rev-parse", "--abbrev-ref", "HEAD"])

    def checkout(self, branch: str, create: bool = False) -> None:
        if create:
            self.run(["checkout", "-b", branch])
        else:
            self.run(["checkout", branch])

    def branch_exists(self, branch: str) -> bool:
        proc = subprocess.run(
            ["git", "show-ref", "--verify", f"refs/heads/{branch}"],
            cwd=self.path,
            text=True,
            capture_output=True,
        )
        return proc.returncode == 0

    def add_all(self) -> None:
        self.run(["add", "-A"])

    def commit(self, message: str) -> None:
        self.run(["commit", "-m", message])


def org_branch(agent_id: str) -> str:
    return f"org/{agent_id}"


def team_branch(lead_id: str) -> str:
    """課(lead)単位のブランチ名（フラット命名）。

    例: lead_id="dev_lead" -> "team-dev_lead"

    NOTE: これは運用ポリシーの土台。
    実際の承認フロー（worker -> lead 承認 -> team branch 反映等）は runtime/pipeline 側で強制する。
    """

    lead_id = lead_id.strip()
    if not lead_id:
        raise ValueError("lead_id is required")
    return f"team-{lead_id}"
