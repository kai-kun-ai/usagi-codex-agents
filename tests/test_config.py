"""config モジュールのテスト。"""

from pathlib import Path

from usagi.config import UsagiConfig


def test_default_config() -> None:
    cfg = UsagiConfig()
    assert cfg.model == "codex"
    assert cfg.max_rounds == 1
    assert cfg.agents == []


def test_load_from_file(tmp_path: Path) -> None:
    yml = tmp_path / ".usagi.yml"
    yml.write_text(
        """
model: gpt-4.1
max_rounds: 3
agents:
  - name: テストうさぎ
    role: coder
    system_prompt: "テスト用プロンプト"
""",
        encoding="utf-8",
    )
    cfg = UsagiConfig.load(yml)
    assert cfg.model == "gpt-4.1"
    assert cfg.max_rounds == 3
    assert len(cfg.agents) == 1
    assert cfg.agents[0].name == "テストうさぎ"


def test_load_missing_file(tmp_path: Path) -> None:
    cfg = UsagiConfig.load(tmp_path / "nonexistent.yml")
    assert cfg.model == "codex"
