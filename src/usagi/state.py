"""状態管理（稼働中/待機中の可視化）。

- `.usagi/status.json` に状態を保存
- watch/autopilot が更新し、CLI `usagi status` が表示する
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path


_WARNED_CORRUPT_STATUS: set[Path] = set()


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


def _warn_corrupt_status(path: Path, *, reason: str) -> None:
    """Write a best-effort warning to `.usagi/events.log`.

    TUI reads this file and shows it to the user.

    We intentionally avoid raising if we cannot write the log.
    """

    # Avoid spamming the event log on every refresh.
    if path in _WARNED_CORRUPT_STATUS:
        return
    _WARNED_CORRUPT_STATUS.add(path)

    try:
        event_log_path = path.parent / "events.log"
        event_log_path.parent.mkdir(parents=True, exist_ok=True)
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        with event_log_path.open("a", encoding="utf-8") as f:
            f.write(f"[{ts}] WARN: status.json is invalid; using empty status ({reason})\n")
    except Exception:
        # best-effort only
        return


def load_status(path: Path) -> SystemStatus:
    if not path.exists():
        return SystemStatus()

    try:
        text = path.read_text(encoding="utf-8")
    except OSError as e:
        _warn_corrupt_status(path, reason=f"read failed: {type(e).__name__}")
        return SystemStatus()

    if text.strip() == "":
        _warn_corrupt_status(path, reason="empty")
        return SystemStatus()

    try:
        raw = json.loads(text)
    except json.JSONDecodeError:
        _warn_corrupt_status(path, reason="JSON decode error")
        return SystemStatus()

    agents: dict[str, AgentStatus] = {}
    for k, v in (raw.get("agents", {}) or {}).items():
        agents[k] = AgentStatus(**v)
    return SystemStatus(agents=agents)


def save_status(path: Path, st: SystemStatus) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = {"agents": {k: asdict(v) for k, v in st.agents.items()}}
    path.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
