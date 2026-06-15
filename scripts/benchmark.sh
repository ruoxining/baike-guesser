#!/usr/bin/env bash
# Benchmark solver algorithms against saved puzzles in puzzles/.
# Run scripts/record_today.sh first to save at least one puzzle.
#
# Usage:
#   bash scripts/benchmark.sh
#   bash scripts/benchmark.sh --algos constraint entropy combined
#   bash scripts/benchmark.sh --puzzle puzzles/20260615.json
#   bash scripts/benchmark.sh --max-guesses 60 --no-save
set -euo pipefail

DIR=$(cd "$(dirname "$0")/.." && pwd)
python3 "$DIR/algo/benchmark.py" "$@"
