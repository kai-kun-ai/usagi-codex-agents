from pathlib import Path

from usagi.tui import _fallback_org_path


def test_fallback_org_path_prefers_existing(tmp_path: Path) -> None:
    org = tmp_path / "org.toml"
    org.write_text("x", encoding="utf-8")
    assert _fallback_org_path(org, tmp_path) == org


def test_fallback_org_path_returns_candidate_when_missing(tmp_path: Path) -> None:
    missing = tmp_path / "missing.toml"
    # repoに examples/org.toml があるならそれにフォールバックする
    resolved = _fallback_org_path(missing, tmp_path)
    assert resolved.name == "org.toml" or resolved == missing
