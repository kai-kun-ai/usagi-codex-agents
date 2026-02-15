"""Tests that the local (non-Docker) smoke-test path works."""

import subprocess
import shutil
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_smoke_script_exists_and_executable():
    script = REPO_ROOT / "scripts" / "smoke-test.sh"
    assert script.exists(), "scripts/smoke-test.sh must exist"
    assert script.stat().st_mode & 0o111, "scripts/smoke-test.sh must be executable"


def test_makefile_has_test_local_target():
    makefile = (REPO_ROOT / "Makefile").read_text()
    assert "test-local:" in makefile, "Makefile must expose a test-local target"


def test_ruff_available():
    assert shutil.which("ruff"), "ruff must be available on PATH"


def test_pytest_available():
    assert shutil.which("pytest"), "pytest must be available on PATH"


def test_usagi_module_importable():
    """Ensure `python -m usagi` resolves (package installed)."""
    r = subprocess.run(
        ["python3", "-c", "import usagi"],
        capture_output=True,
        timeout=15,
    )
    assert r.returncode == 0, f"usagi not importable: {r.stderr.decode()}"
