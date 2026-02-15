from pathlib import Path

from usagi.profiles import load_profiles


def test_load_profiles(tmp_path: Path) -> None:
    p = tmp_path / "profiles.toml"
    p.write_text(
        """
[[profiles]]
name = "a"
codex_config = "/tmp/a.toml"
docker_image = "img:a"

[[profiles]]
name = "b"
codex_config = "/tmp/b.toml"
""",
        encoding="utf-8",
    )
    store = load_profiles(p)
    assert len(store.profiles) == 2
    assert store.get("a") is not None
    assert store.get("a").codex_config == "/tmp/a.toml"
    assert store.get("b").docker_image == "usagi-worker:latest"
    assert store.get("unknown") is None
    assert store.names() == ["a", "b"]


def test_load_profiles_missing() -> None:
    store = load_profiles(Path("/nonexistent/profiles.toml"))
    assert store.profiles == []


def test_agent_profile_field() -> None:
    from usagi.org import AgentDef

    a = AgentDef(id="w1", name="test", role="worker", profile="account_a")
    assert a.profile == "account_a"
