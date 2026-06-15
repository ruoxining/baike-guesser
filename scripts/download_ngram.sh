#!/usr/bin/env bash
# Download Google Books Ngram (20200217, Chinese Simplified) raw shards.
#
# URL format: http://storage.googleapis.com/books/ngrams/books/20200217/chi_sim/
# File format: ngram_POS<TAB>year,count,vol<TAB>...  (one line per ngram)
#
# Usage:
#   bash scripts/download_ngram.sh [max_n]
#   max_n defaults to 2 (1-gram ~58 MB, 2-gram ~2.2 GB compressed)
#   Set max_n=3 to also fetch 3-gram (~17 GB) — takes a long time.
#
# Output: data/google-ngram-zh-2020/raw/{n}gram/*.gz

set -euo pipefail

MAX_N=${1:-2}
BASE="http://storage.googleapis.com/books/ngrams/books/20200217/chi_sim"
OUT="data/google-ngram-zh-2020/raw"

mkdir -p "$OUT"

for n in $(seq 1 "$MAX_N"); do
    exports_url="${BASE}/chi_sim-${n}-ngrams_exports.html"
    echo "=== ${n}-gram: fetching shard list from $exports_url ==="

    shard_urls=$(curl -s "$exports_url" | grep -oP 'href="[^"]*\.gz"' | tr -d 'href="')
    n_shards=$(echo "$shard_urls" | wc -l)
    echo "  $n_shards shard(s) to download"

    mkdir -p "${OUT}/${n}gram"

    i=0
    while IFS= read -r url; do
        fname=$(basename "$url")
        dest="${OUT}/${n}gram/${fname}"
        if [ -f "$dest" ]; then
            echo "  [skip] $fname already exists"
        else
            echo "  downloading $fname ..."
            wget -q "$url" -O "$dest"
        fi
        i=$((i+1))
    done <<< "$shard_urls"

    echo "  done (${i} shards in ${OUT}/${n}gram/)"
done

echo ""
echo "All downloads complete. Next: bash scripts/build_ngram.sh"
