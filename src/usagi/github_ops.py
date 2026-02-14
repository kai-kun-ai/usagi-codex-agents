"""GitHub操作（任意）。

- runtime.gh_enabled が true のときのみ実行
- 組織（agent_id）ごとにPRは作成できる
- PR merge は boss のみ（運用ポリシーとして呼び出し側で制御）

実装は `gh` CLI を利用（GitHub Actions / ローカルで一貫）。
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Gh:
    repo_path: Path

    def run(self, args: list[str]) -> str:
        proc = subprocess.run(
            ["gh", *args],
            cwd=self.repo_path,
            text=True,
            capture_output=True,
            check=False,
        )
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr.strip() or "gh failed")
        return proc.stdout.strip()

    def pr_create(self, title: str, body: str) -> str:
        url = self.run(["pr", "create", "--title", title, "--body", body])
        return url

    def pr_merge(self, pr_number: int) -> None:
        self.run(["pr", "merge", str(pr_number), "--merge"])
