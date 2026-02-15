"""announce のテスト。"""

from usagi.announce import webhook_available


def test_webhook_available_false(monkeypatch) -> None:
    monkeypatch.delenv("USAGI_DISCORD_WEBHOOK_URL", raising=False)
    assert webhook_available() is False
