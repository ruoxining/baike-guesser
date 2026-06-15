#!/usr/bin/env bash
# Build {n}gram.json corpus files from downloaded raw shards.
# Run scripts/download_ngram_v3.sh first to get the raw data.
#
# Usage:
#   bash scripts/build_ngram.sh
#   bash scripts/build_ngram.sh --year-min 1990 --year-max 2019 --min-count 5
set -euo pipefail

DIR=$(cd "$(dirname "$0")/.." && pwd)
python3 "$DIR/data/build_corpus_v3.py" "$@"
