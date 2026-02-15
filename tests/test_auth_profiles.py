"""auth_profiles のテスト。"""

from usagi.auth_profiles import AuthProfileConfig, claude_profile_dir, codex_profile_dir


def test_profile_dirs() -> None:
    cfg = AuthProfileConfig()
    assert codex_profile_dir(cfg, "a").as_posix().endswith(".usagi/sessions/codex/a")
    assert claude_profile_dir(cfg, "b").as_posix().endswith(".usagi/sessions/claude/b")
