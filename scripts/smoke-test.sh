#!/usr/bin/env bash
# smoke-test.sh — Run lint + tests without Docker.
# Falls back gracefully when Docker is unavailable (e.g. no socket permission).
# Usage: bash scripts/smoke-test.sh
set -euo pipefail
cd "$(dirname "$0")/.."

# ---------------------------------------------------------------------------
# 1. Ensure Python test deps are installed
# ---------------------------------------------------------------------------
echo "▸ Installing test dependencies …"
pip install -q -e . ruff pytest pytest-asyncio 2>&1 | tail -1 || true

# ---------------------------------------------------------------------------
# 2. Lint
# ---------------------------------------------------------------------------
echo "▸ ruff check"
ruff check .

# ---------------------------------------------------------------------------
# 3. Tests
# ---------------------------------------------------------------------------
echo "▸ pytest"
pytest -q

# ---------------------------------------------------------------------------
# 4. Module smoke-test
# ---------------------------------------------------------------------------
echo "▸ usagi --help"
python3 -m usagi --help >/dev/null 2>&1 || usagi --help >/dev/null

echo "✅ Smoke tests passed (local, no Docker)"
