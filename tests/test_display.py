from usagi.display import default_emoji_for_role, display_name
from usagi.org import ROLE_BOSS, AgentDef


def test_default_emoji() -> None:
    assert default_emoji_for_role(ROLE_BOSS)


def test_display_name_uses_default() -> None:
    a = AgentDef(id="boss", name="社長うさぎ", role=ROLE_BOSS)
    s = display_name(a)
    assert "社長うさぎ" in s
    assert s.split()[0]


def test_display_name_uses_custom() -> None:
    a = AgentDef(id="x", name="犬", role="worker", emoji="🐶")
    assert display_name(a).startswith("🐶")
