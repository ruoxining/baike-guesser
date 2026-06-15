"""Build {n}gram.json from Google Books Ngram v3 (20200217) raw shards.

v3 format (one line per ngram, all years inline):
    ngram_POS<TAB>year,match_count,volume_count<TAB>...

This script:
  1. Reads all .gz shards from google-ngram-zh-2020/raw/{n}gram/
  2. Strips POS suffixes (_NOUN, _VERB, etc.) and spaces
  3. Keeps only pure CJK character sequences
  4. Filters to a configurable year window and minimum count
  5. Aggregates match counts across years
  6. Writes google-ngram-zh-2020/{n}gram.json
  7. Copies stopwords.txt from the 2012 corpus

Usage:
    python3 scripts/build_corpus_v3.py [--year-min 1990] [--year-max 2019] [--min-count 5]
"""
from __future__ import annotations

import argparse
import gzip
import json
import re
import shutil
from collections import defaultdict
from pathlib import Path

RAW_DIR = Path('google-ngram-zh-2020/raw')
OUT_DIR = Path('google-ngram-zh-2020')
OLD_CORPUS = Path('google-ngram-zh-2012')

_POS_RE = re.compile(r'_([A-Z]+)$')
_CJK_ONLY = re.compile(r'^[一-鿿]+$')

# POS tags in v3 that indicate a proper noun / named entity
_ENTITY_POS = {'PROPN', 'X'}  # PROPN = proper noun; X = other/foreign


def split_pos(raw: str) -> tuple[str, str | None]:
    """Return (clean_token, pos_tag_or_None)."""
    m = _POS_RE.search(raw)
    pos = m.group(1) if m else None
    token = raw[:m.start()] if m else raw
    token = token.replace(' ', '')
    return token, pos


def is_cjk(token: str) -> bool:
    return bool(_CJK_ONLY.match(token))


def process_n(
    n: int, year_min: int, year_max: int, min_count: int
) -> tuple[dict[str, float], set[str]]:
    """Return (freq_dict, entity_ngrams) where entity_ngrams are tagged PROPN/X."""
    shard_dir = RAW_DIR / f'{n}gram'
    if not shard_dir.exists():
        print(f'  {n}gram: no raw shards found at {shard_dir}, skipping')
        return {}, set()

    shards = sorted(shard_dir.glob('*.gz'))
    if not shards:
        print(f'  {n}gram: directory exists but no .gz files, skipping')
        return {}, set()

    freqs: dict[str, float] = defaultdict(float)
    entities: set[str] = set()
    lines_read = 0

    for shard in shards:
        print(f'    {shard.name} ...', end='', flush=True)
        with gzip.open(shard, 'rt', encoding='utf-8', errors='replace') as f:
            for line in f:
                lines_read += 1
                parts = line.rstrip('\n').split('\t')
                if len(parts) < 2:
                    continue
                token, pos = split_pos(parts[0])
                if len(token) != n or not is_cjk(token):
                    continue
                total = 0
                for entry in parts[1:]:
                    try:
                        yr, cnt, _ = entry.split(',')
                        if year_min <= int(yr) <= year_max:
                            total += int(cnt)
                    except ValueError:
                        continue
                if total >= min_count:
                    freqs[token] += total
                    if pos in _ENTITY_POS:
                        entities.add(token)
        print(f' {len(freqs):,} entries so far')

    print(f'  {n}gram: {lines_read:,} lines → {len(freqs):,} CJK ngrams, {len(entities):,} entities')
    return dict(freqs), entities


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--year-min', type=int, default=1990)
    parser.add_argument('--year-max', type=int, default=2019)
    parser.add_argument('--min-count', type=int, default=5,
                        help='minimum total match count across the year window')
    parser.add_argument('--max-n', type=int, default=6)
    args = parser.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print(f'Building v3 corpus: years {args.year_min}–{args.year_max}, min_count={args.min_count}')

    for n in range(1, args.max_n + 1):
        print(f'\n--- {n}-gram ---')
        freqs, entities = process_n(n, args.year_min, args.year_max, args.min_count)
        if not freqs:
            continue

        out_path = OUT_DIR / f'{n}gram.json'
        with out_path.open('w', encoding='utf-8') as f:
            json.dump(freqs, f, ensure_ascii=False)
        print(f'  written → {out_path}')

        # Seed tags with POS-derived entity labels (tag_ngrams.py will merge/extend these)
        if entities:
            tags_path = OUT_DIR / f'{n}gram_tags.json'
            existing: dict = {}
            if tags_path.exists():
                with tags_path.open('r', encoding='utf-8') as f:
                    existing = json.load(f)
            for token in entities:
                existing.setdefault(token, {})['is_entity'] = True
            with tags_path.open('w', encoding='utf-8') as f:
                json.dump(existing, f, ensure_ascii=False)
            print(f'  seeded {len(entities):,} entity tags → {tags_path}')

    # Copy stopwords from 2012 corpus
    sw_src = OLD_CORPUS / 'stopwords.txt'
    sw_dst = OUT_DIR / 'stopwords.txt'
    if sw_src.exists() and not sw_dst.exists():
        shutil.copy(sw_src, sw_dst)
        print(f'\ncopied stopwords.txt → {sw_dst}')

    print('\nDone. Run: python3 scripts/tag_ngrams.py --corpus google-ngram-zh-2020')


if __name__ == '__main__':
    main()
