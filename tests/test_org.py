"""org (組織TOML) のテスト。"""

from pathlib import Path

from usagi.org import default_org, load_org


def test_default_org_has_boss_and_departments() -> None:
    org = default_org()
    assert org.boss.name == "社長うさぎ"
    assert len(org.departments) == 2
    assert org.find_agent("実装うさぎ") is not None


def test_load_org_from_toml(tmp_path: Path) -> None:
    toml = tmp_path / "org.toml"
    toml.write_text(
        """
[boss]
name = "社長うさぎ"
role = "boss"
model = "gpt-4.1"

[[departments]]
name = "開発部"

[departments.manager]
name = "開発部長うさぎ"
role = "manager"
model = "codex"

[[departments.members]]
name = "実装うさぎA"
role = "coder"

[[departments]]
name = "レビュー部"

[departments.manager]
name = "レビュー部長うさぎ"
role = "manager"

[[departments.members]]
name = "監査うさぎA"
role = "reviewer"
""",
        encoding="utf-8",
    )

    org = load_org(toml)
    assert org.boss.model == "gpt-4.1"
    assert len(org.departments) == 2
    assert org.find_agent("実装うさぎA") is not None
    assert org.find_agent("監査うさぎA") is not None
