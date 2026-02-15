"""usagi の設定ファイル(.usagi.yml)のロードと管理。

プロジェクトルートに `.usagi.yml` を置くと、
カスタムエージェントやモデル設定を上書きできる。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class AgentConfig:
    name: str
    role: str  # planner | coder | reviewer
    system_prompt: str = ""


@dataclass
class UsagiConfig:
    model: str = "codex"
    max_rounds: int = 1
    agents: list[AgentConfig] = field(default_factory=list)

    @classmethod
    def load(cls, path: Path | None = None) -> UsagiConfig:
        """設定ファイルを読み込む。なければデフォルト。"""
        if path is None:
            path = Path(".usagi.yml")
        if not path.exists():
            return cls()
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        agents = []
        for a in raw.get("agents", []):
            agents.append(
                AgentConfig(
                    name=a.get("name", "名無しうさぎ"),
                    role=a.get("role", "coder"),
                    system_prompt=a.get("system_prompt", ""),
                )
            )
        return cls(
            model=raw.get("model", "codex"),
            max_rounds=int(raw.get("max_rounds", 1)),
            agents=agents,
        )
