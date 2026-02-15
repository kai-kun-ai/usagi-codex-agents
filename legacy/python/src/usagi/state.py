"""状態管理（稼働中/待機中の可視化）。

- `.usagi/status.json` に状態を保存
- watch/autopilot が更新し、CLI `usagi status` が表示する
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class AgentStatus:
    agent_id: str
    name: str
    state: str = "idle"  # idle | working | blocked
    task: str = ""
    updated_at: float = field(default_factory=lambda: time.time())


@dataclass
class SystemStatus:
    agents: dict[str, AgentStatus] = field(default_factory=dict)

    def set(self, s: AgentStatus) -> None:
        s.updated_at = time.time()
        self.agents[s.agent_id] = s


def load_status(path: Path) -> SystemStatus:
    if not path.exists():
        return SystemStatus()
    raw = json.loads(path.read_text(encoding="utf-8"))
    agents: dict[str, AgentStatus] = {}
    for k, v in (raw.get("agents", {}) or {}).items():
        agents[k] = AgentStatus(**v)
    return SystemStatus(agents=agents)


def save_status(path: Path, st: SystemStatus) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = {"agents": {k: asdict(v) for k, v in st.agents.items()}}
    path.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
