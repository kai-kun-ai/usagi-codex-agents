"""CLI backend: 外部CLI（codex/claude等）をstdin/stdoutで呼ぶ。

このプロジェクトはDocker前提で、CLI実体はコンテナ内にインストールされている想定。
（未インストールの場合はエラーメッセージで案内する）
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass


@dataclass
class CLIBackend:
    command: list[str]
    timeout_seconds: int = 120

    def run(self, prompt: str, *, env: dict[str, str] | None = None) -> str:
        try:
            proc = subprocess.run(
                self.command,
                input=prompt,
                text=True,
                capture_output=True,
                timeout=self.timeout_seconds,
                check=False,
                env=env,
            )
        except FileNotFoundError as e:
            raise RuntimeError(f"CLI not found: {self.command[0]}") from e

        if proc.returncode != 0:
            msg = proc.stderr.strip() or f"CLI failed: {self.command}"
            raise RuntimeError(msg)
        return proc.stdout
