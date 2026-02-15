"""TUI の表示テスト（Textual async pilot）。"""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from usagi.tui import UsagiTui


@pytest.fixture()
def work_root(tmp_path: Path) -> Path:
    """最小限の作業ディレクトリを作る。"""
    usagi = tmp_path / ".usagi"
    usagi.mkdir()

    # events log
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    (usagi / "events.log").write_text(
        f"[{ts}] test_event: hello\n", encoding="utf-8"
    )

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
    (usagi / "secretary.log").write_text(
        f"[{ts}] you: test message\n", encoding="utf-8"
    )

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


@pytest.mark.asyncio()
async def test_tui_shows_status(work_root: Path, org_path: Path) -> None:
    app = UsagiTui(
        root=work_root,
        org_path=org_path,
        model="codex",
        offline=True,
        demo=False,
    )
    async with app.run_test() as pilot:
        await pilot.pause()
        # status box should show agent info
        status_text = app.query_one("#status").render()
        assert status_text is not None


@pytest.mark.asyncio()
async def test_tui_shows_events(work_root: Path, org_path: Path) -> None:
    app = UsagiTui(
        root=work_root,
        org_path=org_path,
        model="codex",
        offline=True,
        demo=False,
    )
    async with app.run_test() as pilot:
        await pilot.pause()
        events_text = app.query_one("#events").render()
        assert events_text is not None


@pytest.mark.asyncio()
async def test_tui_shows_org(work_root: Path, org_path: Path) -> None:
    app = UsagiTui(
        root=work_root,
        org_path=org_path,
        model="codex",
        offline=True,
        demo=False,
    )
    async with app.run_test() as pilot:
        await pilot.pause()
        org_text = app.query_one("#org").render()
        assert org_text is not None


@pytest.mark.asyncio()
async def test_tui_secretary_chat_input(work_root: Path, org_path: Path) -> None:
    """秘書チャットに入力して submit すると secretary.log に追記される。"""
    app = UsagiTui(
        root=work_root,
        org_path=org_path,
        model="codex",
        offline=True,
        demo=False,
    )
    async with app.run_test() as pilot:
        inp = app.query_one("#secretary_input")
        inp.focus()
        await pilot.pause()
        await pilot.press("h", "i")
        await pilot.press("enter")
        await pilot.pause()

        log = work_root / ".usagi/secretary.log"
        assert log.exists()
        content = log.read_text(encoding="utf-8")
        assert "hi" in content


@pytest.mark.asyncio()
async def test_tui_mode_toggle_button(work_root: Path, org_path: Path) -> None:
    """modeボタンで .usagi/STOP がトグルされる。"""
    app = UsagiTui(
        root=work_root,
        org_path=org_path,
        model="codex",
        offline=True,
        demo=False,
    )
    async with app.run_test() as pilot:
        await pilot.pause()
        # toggle to stop
        await pilot.click("#mode")
        await pilot.pause()
        assert (work_root / ".usagi/STOP").exists()

        # toggle back to running
        await pilot.click("#mode")
        await pilot.pause()
        assert not (work_root / ".usagi/STOP").exists()
