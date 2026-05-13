#!/usr/bin/env bash
# compile_translations.sh
# Compiles all .po files to .mo using Python (no gettext CLI required).
# Run from the repo root: bash scripts/compile_translations.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python3 "$SCRIPT_DIR/compile_translations.py"
