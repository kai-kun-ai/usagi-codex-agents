"""autopilot: 止めるまで走る常駐モード。

現段階では以下を提供:
- start: watch をフォアグラウンド実行（まずは確実に動く形）
- status: stateファイルの存在など簡易表示
- stop: stopファイルを書いて watch ループ側が停止する

次のPRで Discord stop コマンドや PID 管理を強化する。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class AutopilotPaths:
    root: Path

    @property
    def stop_file(self) -> Path:
        return self.root / ".usagi" / "STOP"

    @property
    def state_file(self) -> Path:
        return self.root / ".usagi" / "state.json"


def request_stop(root: Path) -> Path:
    paths = AutopilotPaths(root)
    paths.stop_file.parent.mkdir(parents=True, exist_ok=True)
    paths.stop_file.write_text("stop", encoding="utf-8")
    return paths.stop_file


def clear_stop(root: Path) -> None:
    paths = AutopilotPaths(root)
    if paths.stop_file.exists():
        paths.stop_file.unlink()


def stop_requested(root: Path) -> bool:
    return AutopilotPaths(root).stop_file.exists()
