from __future__ import annotations

import json
import time
from pathlib import Path

import pytest


@pytest.fixture()
def work_root(tmp_path: Path) -> Path:
    """最小限の作業ディレクトリを作る。"""
    usagi = tmp_path / ".usagi"
    usagi.mkdir()

    # events log
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    (usagi / "events.log").write_text(f"[{ts}] test_event: hello\n", encoding="utf-8")

    # status.json
    (usagi / "status.json").write_text(
        json.dumps(
            {
                "agents": {
                    "w1": {
                        "agent_id": "w1",
                        "name": "実装リスA",
                        "state": "working",
                        "task": "fizzbuzz",
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    # inputs
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    (inputs / "hello.md").write_text("# Hello", encoding="utf-8")

    # secretary.log
    (usagi / "secretary.log").write_text(f"[{ts}] you: test message\n", encoding="utf-8")

    return tmp_path


@pytest.fixture()
def org_path(tmp_path: Path) -> Path:
    p = tmp_path / "org.toml"
    p.write_text(
        """
[[agents]]
id = "boss"
name = "社長うさぎ"
emoji = "🐰"
role = "boss"
reports_to = ""

[[agents]]
id = "w1"
name = "実装リスA"
emoji = "🐿️"
role = "worker"
reports_to = "boss"
""",
        encoding="utf-8",
    )
    return p
