"""Discord投稿フォーマットのテスト。"""

from usagi.discord_client import format_message


def test_format_message_prefix() -> None:
    assert format_message("社長うさぎ", "hi") == "[社長うさぎ] hi"


def test_sanitize_everyone() -> None:
    msg = format_message("A", "@everyone hello")
    assert "@everyone" not in msg
