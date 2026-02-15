from __future__ import annotations

from pathlib import Path

import pytest

from usagi.tui import UsagiTui


@pytest.mark.asyncio()
async def test_tui_inputs_delete_moves_to_trash(tmp_path: Path) -> None:
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
    target = inputs / "a.md"
    target.write_text("# a", encoding="utf-8")

    app = UsagiTui(root=root, org_path=org, model="codex", offline=True, demo=False)

    async with app.run_test() as pilot:
        await pilot.pause()
        # inputs listにフォーカスしてから d で削除
        app.query_one("#inputs").focus()
        await pilot.pause()
        await pilot.press("d")
        await pilot.pause(0.6)

    assert not target.exists()
    trash_dir = root / ".usagi/trash/inputs"
    assert trash_dir.exists()
    assert any(p.name.endswith("-a.md") for p in trash_dir.iterdir())
