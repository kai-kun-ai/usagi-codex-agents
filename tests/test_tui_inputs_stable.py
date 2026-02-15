from __future__ import annotations

from pathlib import Path

import pytest

from usagi.tui import UsagiTui


@pytest.mark.asyncio()
async def test_tui_inputs_refresh_is_stable_when_unchanged(tmp_path: Path) -> None:
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

    inputs = root / "inputs"
    inputs.mkdir()
    (inputs / "a.md").write_text("# a", encoding="utf-8")

    app = UsagiTui(root=root, org_path=org, model="codex", offline=True, demo=False)

    async with app.run_test() as pilot:
        await pilot.pause(0.6)

        lv = app.query_one("#inputs")
        # ListView's children are ListItem widgets
        first_item_before = next(iter(lv.children))

        # Refresh again without changing files.
        lv.refresh_items()
        await pilot.pause(0.1)

        first_item_after = next(iter(lv.children))

    # If refresh is stable, widgets should not be recreated.
    assert first_item_before is first_item_after
