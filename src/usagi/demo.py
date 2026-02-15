"""デモ/ダミーモード。

目的:
- APIや外部CLIを一切叩かずに、CUI(TUI)が「それっぽく動く」様子を再現する
- inputs/status/events/outputs を疑似的に更新し、画面の見た目を確認できるようにする

注意:
- secrets は扱わない
- `.usagi/STOP` がある場合は停止する
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass
from pathlib import Path

from usagi.autopilot import stop_requested
from usagi.display import display_name
from usagi.org import load_org
from usagi.state import AgentStatus, load_status, save_status


@dataclass
class DemoConfig:
    root: Path
    org_path: Path | None = None
    interval_seconds: float = 1.0


def _append_event(path: Path, msg: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    with path.open("a", encoding="utf-8") as f:
        f.write(f"[{ts}] {msg}\n")


def run_demo_forever(cfg: DemoConfig) -> None:
    root = cfg.root
    (root / "inputs").mkdir(parents=True, exist_ok=True)
    (root / "outputs").mkdir(parents=True, exist_ok=True)
    (root / ".usagi").mkdir(parents=True, exist_ok=True)

    events = root / ".usagi/events.log"
    status_path = root / ".usagi/status.json"

    agents: list[tuple[str, str]]
    if cfg.org_path and cfg.org_path.exists():
        try:
            org = load_org(cfg.org_path)
            agents = [(a.id, display_name(a)) for a in org.agents]
        except Exception:
            agents = [("boss", "🐰 社長うさぎ")]
    else:
        agents = [
            ("boss", "🐰 社長うさぎ"),
            ("dev_mgr", "🦊 開発部長キツネ"),
            ("w1", "🐿️ 実装リスA"),
            ("w2", "🐿️ 実装リスB"),
            ("qa_mgr", "🦝 品質部長アライグマ"),
            ("rev1", "🦉 監査フクロウ"),
        ]

    step_msgs = [
        "仕様を読み込み中…",
        "タスクを分解中…",
        "実装中…",
        "テスト中…",
        "レポート生成中…",
    ]

    i = 0
    while True:
        if stop_requested(root):
            _append_event(events, "DEMO: STOP requested -> demo halted")
            break

        # occasionally create/update an input
        if i % 5 == 0:
            p = root / "inputs" / f"demo-{i//5:03d}.md"
            p.write_text(
                "# usagi spec\n\n" f"title: demo {i//5:03d}\n" "\n## request\n\nデモです。\n",
                encoding="utf-8",
            )
            _append_event(events, f"DEMO: input updated: {p.name}")

            # also write a fake output
            out = root / "outputs" / f"demo-{i//5:03d}.report.md"
            out.write_text(
                "# DEMO report\n\n- This is a demo output.\n",
                encoding="utf-8",
            )

        # update status
        st = load_status(status_path)
        for agent_id, name in agents:
            # boss tends to be working
            working = random.random() < (0.6 if agent_id == "boss" else 0.35)
            state = "working" if working else "idle"
            task = random.choice(step_msgs) if working else ""
            st.set(AgentStatus(agent_id=agent_id, name=name, state=state, task=task))
        save_status(status_path, st)

        # emit a little progress line
        _append_event(events, f"DEMO: tick {i:04d}")

        i += 1
        time.sleep(cfg.interval_seconds)
