from pathlib import Path

from usagi.approval_pipeline import run_approval_pipeline
from usagi.org import default_org
from usagi.runtime import RuntimeMode
from usagi.spec import parse_spec_markdown


def test_approval_pipeline_offline_runs(tmp_path: Path) -> None:
    spec = parse_spec_markdown(
        """
# usagi spec

title: test

## objective

do thing

## tasks

- a
"""
    )
    org = default_org()
    runtime = RuntimeMode()

    res = run_approval_pipeline(
        spec=spec,
        workdir=tmp_path / "work",
        model="codex",
        offline=True,
        org=org,
        runtime=runtime,
        root=tmp_path,
    )

    assert "うさぎさん株式会社レポート" in res.report
    # boss plan + worker impl + lead review + manager decision
    assert len(res.messages) >= 4
