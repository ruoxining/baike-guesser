#!/usr/bin/env bash
# Fetch today's Baike puzzle and save to puzzles/
#   ./record_today.sh
#   ./record_today.sh --date 20260604
#   ./record_today.sh --sub-type history
set -euo pipefail

DIR=$(cd "$(dirname "$0")/.." && pwd)
python3 "$DIR/record_puzzle.py" "$@"
