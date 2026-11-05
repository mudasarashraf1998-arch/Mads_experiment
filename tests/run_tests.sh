#!/bin/bash
# Run the automated test suite for Universal Downloader 2.0.2.
# No real downloads are performed; downloader subprocesses are mocked.
set -euo pipefail

ROOT="$(cd -P "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if ! python3 -m pytest --version >/dev/null 2>&1; then
  python3 -m pip install --break-system-packages -q pytest pytest-mock
fi

python3 -m pytest -v "$@"
