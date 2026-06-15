#!/bin/bash
# Download Google Books Ngram v3 (20200217) — Chinese Simplified.
#
# v3 uses a different URL and file structure from v2:
#   URL:    http://storage.googleapis.com/books/ngrams/books/20200217/chi_sim/{n}-{shard}-of-{total}.gz
#   Format: ngram_POS<TAB>year,count,vol<TAB>year,count,vol...   (one line per ngram)
#
# Usage:
#   bash scripts/download_ngram_v3.sh [max_n]
#   max_n defaults to 2 (1-gram ~58MB, 2-gram ~2.2GB compressed)
#   Set max_n=3 to also get 3-gram (~17GB compressed) — takes a long time.
#
# Output: google-ngram-zh-2020/raw/{n}gram/*.gz

set -euo pipefail

MAX_N=${1:-2}
BASE="http://storage.googleapis.com/books/ngrams/books/20200217/chi_sim"
OUT="google-ngram-zh-2020/raw"

mkdir -p "$OUT"

for n in $(seq 1 "$MAX_N"); do
    exports_url="${BASE}/chi_sim-${n}-ngrams_exports.html"
    echo "=== ${n}-gram: fetching shard list from $exports_url ==="

    # Parse shard URLs from the exports page
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
echo "All downloads complete. Run: python3 scripts/build_corpus_v3.py"
