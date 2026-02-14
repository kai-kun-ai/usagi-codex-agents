"""github_ops のテスト（gh CLIが無い環境ではskip）。"""

from pathlib import Path

import pytest

from usagi.github_ops import Gh


def test_gh_missing_skips(tmp_path: Path) -> None:
    gh = Gh(tmp_path)
    try:
        gh.run(["--version"])
    except RuntimeError:
        pytest.skip("gh not available")
