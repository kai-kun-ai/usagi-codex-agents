"""report モジュールのテスト。"""

from pathlib import Path

from usagi.agents import AgentMessage
from usagi.report import render_report
from usagi.spec import UsagiSpec


def test_render_report_basic() -> None:
    spec = UsagiSpec(project="test", objective="テスト目的", tasks=["task1"])
    messages = [
        AgentMessage(agent_name="社長うさぎ", role="planner", content="計画です"),
        AgentMessage(agent_name="実装うさぎ", role="coder", content="差分です"),
        AgentMessage(agent_name="監査うさぎ", role="reviewer", content="LGTM"),
    ]
    report = render_report(
        spec=spec,
        workdir=Path("/tmp/test"),
        started="2026-01-01T00:00:00Z",
        messages=messages,
        actions=["git apply OK"],
    )
    assert "# 🐰 うさぎさん株式会社レポート" in report
    assert "test" in report
    assert "テスト目的" in report
    assert "👔 社長うさぎ" in report
    assert "💻 実装うさぎ" in report
    assert "🔍 監査うさぎ" in report
    assert "git apply OK" in report


def test_render_report_empty_tasks() -> None:
    spec = UsagiSpec(project="empty")
    report = render_report(
        spec=spec,
        workdir=Path("/tmp"),
        started="2026-01-01T00:00:00Z",
        messages=[],
        actions=[],
    )
    assert "(なし)" in report
