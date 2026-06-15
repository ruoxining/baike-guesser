#!/usr/bin/env bash
# Merge the 2012 (v2) and 2020 (v3) corpora into data/google-ngram-zh/.
# Run scripts/build_ngram.sh and scripts/tag_ngrams.sh for both corpora first.
#
# Usage:
#   bash scripts/merge_ngram.sh
set -euo pipefail

DIR=$(cd "$(dirname "$0")/.." && pwd)
python3 "$DIR/data/merge_corpus.py"
