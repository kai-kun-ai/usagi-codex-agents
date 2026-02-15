"""cli_backend のテスト。"""

import usagi.cli_backend as m


def test_cli_backend_missing_binary() -> None:
    b = m.CLIBackend(["definitely-not-a-real-binary-xyz"], timeout_seconds=1)
    try:
        b.run("hi")
        assert False, "should raise"  # noqa: B011
    except RuntimeError as e:
        assert "CLI not found" in str(e)
