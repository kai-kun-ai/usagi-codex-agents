"""TUI の表示テスト（Textual async pilot）。

Fixtures are defined in tests/conftest.py.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from usagi.tui import UsagiTui


@pytest.mark.asyncio()
async def test_tui_shows_status_in_org(work_root: Path, org_path: Path) -> None:
    """状態表示は組織図に統合されている。"""
    app = UsagiTui(
        root=work_root,
        org_path=org_path,
        model="codex",
        offline=True,
        demo=False,
    )
    async with app.run_test() as pilot:
        await pilot.pause()
        org_renderable = app.query_one("#org").render()
        assert org_renderable is not None


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
@pytest.mark.skip(reason="secretary_to_input runs async summarize; needs offline stub (see #77)")
async def test_tui_secretary_to_input_shortcut(work_root: Path, org_path: Path) -> None:
    """ボタン無しでも操作できるよう、ショートカットで起票できる。"""
    # Pre-populate secretary.log so ctrl+b has content to submit
    sec_log = work_root / ".usagi" / "secretary.log"
    sec_log.parent.mkdir(parents=True, exist_ok=True)
    sec_log.write_text("テスト入力\n", encoding="utf-8")

    app = UsagiTui(
        root=work_root,
        org_path=org_path,
        model="codex",
        offline=True,
        demo=False,
    )
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("ctrl+b")
        await pilot.pause(1.5)

        placed = list((work_root / "inputs" / "secretary").glob("*.md"))
        assert placed, "expected inputs/secretary/*.md to be created"


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
        await pilot.pause(0.6)
        assert (work_root / ".usagi/STOP").exists()

        # toggle back to running
        await pilot.click("#mode")
        await pilot.pause(0.6)
        assert not (work_root / ".usagi/STOP").exists()
