from __future__ import annotations

from pathlib import Path

import pytest

from usagi.tui import UsagiTui


@pytest.mark.asyncio()
async def test_tui_secretary_input_does_not_overlap_events(tmp_path: Path) -> None:
    """Regression for #68.

    When the secretary input area becomes tall (e.g. wrapped / expanded),
    it must not overlap the events log area.
    """

    root = tmp_path
    (root / ".usagi").mkdir()

    # minimal org
    org = root / "org.toml"
    org.write_text(
        """
[[agents]]
id = "boss"
name = "B"
emoji = "🐰"
role = "boss"
reports_to = ""
""",
        encoding="utf-8",
    )

    app = UsagiTui(root=root, org_path=org, model="codex", offline=True, demo=False)

    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()

        secretary_input = app.query_one("#secretary_input")
        events = app.query_one("#events")

        # Simulate the input becoming tall (the real bug manifests when it grows vertically)
        secretary_input.styles.height = 10

        # Let layout settle
        await pilot.pause()
        app.refresh(layout=True)
        await pilot.pause()

        input_bottom = secretary_input.region.y + secretary_input.region.height
        events_top = events.region.y

        assert input_bottom <= events_top, (
            f"secretary_input overlaps events: input_bottom={input_bottom}, events_top={events_top}"
        )
