"""org (組織TOML) のテスト。"""

from pathlib import Path

from usagi.org import ROLE_LEAD, ROLE_MANAGER, ROLE_WORKER, default_org, load_org


def test_default_org_has_hierarchy() -> None:
    org = default_org()
    boss = org.find("boss")
    assert boss is not None

    dev_mgr = org.find("dev_mgr")
    assert dev_mgr is not None
    assert dev_mgr.role == ROLE_MANAGER

    lead = org.find("dev_lead")
    assert lead is not None
    assert lead.role == ROLE_LEAD
    assert lead.reports_to == "dev_mgr"

    worker1 = org.find("worker1")
    assert worker1 is not None
    assert worker1.role == ROLE_WORKER
    assert worker1.reports_to == "dev_lead"

    # manager -> lead -> worker
    assert org.can_command("dev_mgr", "dev_lead") is True
    assert org.can_command("dev_lead", "worker1") is True


def test_load_org_new_format(tmp_path: Path) -> None:
    toml = tmp_path / "org.toml"
    toml.write_text(
        """
[[agents]]
id = "boss"
name = "社長うさぎ"
role = "boss"

[[agents]]
id = "mgr"
name = "部長うさぎ"
role = "manager"
reports_to = "boss"
can_command = ["w1"]

[[agents]]
id = "w1"
name = "ワーカー1"
role = "worker"
reports_to = "mgr"
""",
        encoding="utf-8",
    )

    org = load_org(toml)
    assert org.find("boss") is not None
    assert org.can_command("mgr", "w1") is True


def test_load_org_legacy_format(tmp_path: Path) -> None:
    toml = tmp_path / "org.toml"
    toml.write_text(
        """
[boss]
name = "社長うさぎ"
model = "gpt-4.1"

[[departments]]
name = "開発部"

[departments.manager]
name = "開発部長うさぎ"
role = "manager"
model = "codex"

[[departments.members]]
name = "実装うさぎA"
role = "coder"  # 互換でworker扱い
""",
        encoding="utf-8",
    )

    org = load_org(toml)
    assert org.find("boss") is not None

    # legacy manager id is mgr1
    mgr = org.find("mgr1")
    assert mgr is not None

    # member id is mgr1_m1
    mem = org.find("mgr1_m1")
    assert mem is not None
    assert mem.role == ROLE_WORKER
    assert mem.reports_to == "mgr1"
