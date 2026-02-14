"""mcp_stdin のテスト（dispatchの最小確認）。"""

from usagi.mcp_stdin import StdinMCP, Tool


def test_dispatch_echo() -> None:
    m = StdinMCP([Tool(name="echo", description="", schema={})])
    assert m._dispatch("echo", {"text": "hi"})["output"] == "hi"  # noqa: SLF001
