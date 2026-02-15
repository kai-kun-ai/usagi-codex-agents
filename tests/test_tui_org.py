from pathlib import Path

from usagi.org import load_org


def test_org_load_examples() -> None:
    p = Path("examples/org.toml")
    assert p.exists()
    org = load_org(p)
    assert len(org.agents) >= 1
