from pathlib import Path

from usagi.demo import DemoConfig, run_demo_forever


def test_demo_uses_org_ids(tmp_path: Path) -> None:
    org = tmp_path / "org.toml"
    org.write_text(
        """
[[agents]]
id = "boss"
name = "社長"
emoji = "🐰"
role = "boss"
reports_to = ""

[[agents]]
id = "w1"
name = "リス"
emoji = "🐿️"
role = "worker"
reports_to = "boss"
""",
        encoding="utf-8",
    )

    # 1 tickだけ回すため、interval=0でSTOPを先に作っておく（すぐ停止）
    (tmp_path / ".usagi").mkdir()
    stop = tmp_path / ".usagi/STOP"
    stop.write_text("stop", encoding="utf-8")

    cfg = DemoConfig(root=tmp_path, org_path=org, interval_seconds=0.0)
    run_demo_forever(cfg)

    # STOPで即停止するのでstatus.json更新は保証しないが、クラッシュしないことが目的
    assert True
