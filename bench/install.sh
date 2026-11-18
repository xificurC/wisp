#!/usr/bin/env bash
# Fallback installer: self-contained harbor venv at bench/.venv.
# Not needed while the curated-terminal-benchmark venv still provides
# harbor; bench/bin/harbor falls back to it automatically.
set -euo pipefail
BENCH_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python3 -m venv "$BENCH_DIR/.venv"
"$BENCH_DIR/.venv/bin/pip" install --upgrade pip
"$BENCH_DIR/.venv/bin/pip" install 'harbor==0.24.0'
"$BENCH_DIR/bin/harbor" --version
