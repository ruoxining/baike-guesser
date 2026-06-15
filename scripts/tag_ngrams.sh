#!/usr/bin/env bash
# Tag ngram JSON files with domain and entity labels.
# Run scripts/build_ngram.sh first to build the corpus JSON files.
#
# Usage:
#   bash scripts/tag_ngrams.sh
#   bash scripts/tag_ngrams.sh --corpus google-ngram-zh
set -euo pipefail

DIR=$(cd "$(dirname "$0")/.." && pwd)
python3 "$DIR/data/tag_ngrams.py" "$@"
