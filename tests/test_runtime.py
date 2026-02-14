"""runtime モード設定のテスト。"""

from pathlib import Path

from usagi.runtime import load_runtime


def test_load_default_runtime_missing_file(tmp_path: Path) -> None:
    mode = load_runtime(tmp_path / "missing.toml")
    assert mode.name == "manual"
    assert mode.merge.policy == "ask_human"
    assert mode.vote.enabled is True


def test_load_runtime_from_file(tmp_path: Path) -> None:
    p = tmp_path / "usagi.runtime.toml"
    p.write_text(
        """
[mode]
name = "auto"

[merge]
policy = "auto_on_ci_green"
require_human_on = ["security"]

[vote]
enabled = false

[autopilot]
enabled = true
inputs_dir = "in"
outputs_dir = "out"
work_root = "work"
stop_commands = ["STOP_USAGI"]
""",
        encoding="utf-8",
    )

    mode = load_runtime(p)
    assert mode.name == "auto"
    assert mode.merge.policy == "auto_on_ci_green"
    assert mode.merge.require_human_on == ["security"]
    assert mode.vote.enabled is False
    assert mode.autopilot.enabled is True
    assert mode.autopilot.inputs_dir == "in"
