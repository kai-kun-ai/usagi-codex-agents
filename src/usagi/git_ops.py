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
        self.run(["init"])

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
