from pathlib import Path

import pytest

from usagi.tui import UsagiTui


@pytest.mark.asyncio()
async def test_secretary_submit_archives_and_clears_log(work_root: Path, org_path: Path) -> None:
    app = UsagiTui(
        root=work_root,
        org_path=org_path,
        model="codex",
        offline=True,
        demo=False,
    )
    async with app.run_test() as pilot:
        await pilot.pause()
        # write something to secretary log via input
        inp = app.query_one("#secretary_input")
        inp.focus()
        await pilot.pause()
        await pilot.press("h", "i")
        await pilot.press("enter")
        await pilot.pause()

        log = work_root / ".usagi/secretary.log"
        assert log.exists()
        assert "hi" in log.read_text(encoding="utf-8")

        # submit
        await pilot.press("ctrl+b")
        await pilot.pause(0.6)

        # log cleared
        assert log.read_text(encoding="utf-8") == ""

        # archived
        archive = work_root / ".usagi/secretary.archive.log"
        assert archive.exists()
        assert "submitted" in archive.read_text(encoding="utf-8")
        assert "hi" in archive.read_text(encoding="utf-8")
