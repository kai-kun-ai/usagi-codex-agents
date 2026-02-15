from __future__ import annotations

from usagi.tui import _focused_window_label


class _FakeFocused:
    def __init__(self, *, id: str | None = None, ancestors: set[str] | None = None):
        self.id = id
        self._ancestors = ancestors or set()

    def has_ancestor(self, selector: str) -> bool:
        return selector in self._ancestors


def test_focused_window_label_none() -> None:
    assert _focused_window_label(None) == "(none)"


def test_focused_window_label_direct_ids() -> None:
    assert _focused_window_label(_FakeFocused(id="mode")) == "mode"
    assert _focused_window_label(_FakeFocused(id="inputs")) == "入力"
    assert _focused_window_label(_FakeFocused(id="secretary_input")) == "秘書入力"


def test_focused_window_label_resolves_by_ancestor() -> None:
    assert _focused_window_label(_FakeFocused(id=None, ancestors={"#inputs"})) == "入力"
    assert (
        _focused_window_label(_FakeFocused(id=None, ancestors={"#secretary_scroll"})) == "秘書ログ"
    )
    assert _focused_window_label(_FakeFocused(id=None, ancestors={"#org_scroll"})) == "組織図"


def test_focused_window_label_fallbacks() -> None:
    assert _focused_window_label(_FakeFocused(id="something")) == "something"
