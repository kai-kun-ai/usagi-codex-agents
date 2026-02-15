"""agents モジュールのテスト。"""

from usagi.agents import JISSOU_USAGI, KANSA_USAGI, SHACHO_USAGI, OfflineBackend


def test_shacho_usagi_offline() -> None:
    backend = OfflineBackend()
    msg = SHACHO_USAGI.run(user_prompt="テスト", model="codex", backend=backend)
    assert msg.agent_name == "社長うさぎ"
    assert msg.role == "planner"
    assert "offline" in msg.content


def test_jissou_usagi_offline() -> None:
    backend = OfflineBackend()
    msg = JISSOU_USAGI.run(user_prompt="テスト", model="codex", backend=backend)
    assert msg.agent_name == "実装うさぎ"
    assert msg.role == "coder"


def test_kansa_usagi_offline() -> None:
    backend = OfflineBackend()
    msg = KANSA_USAGI.run(user_prompt="テスト", model="codex", backend=backend)
    assert msg.agent_name == "監査うさぎ"
    assert msg.role == "reviewer"
