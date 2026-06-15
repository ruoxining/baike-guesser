"""Merge v2 (2012) and v3 (2020) ngram corpora into google-ngram-zh/.

Strategy:
  - Frequencies: sum across sources (both corpora vote; stable ngrams get higher weight).
  - Tags: union (any domain/entity tag from either source is kept; conflicts prefer v3).
  - 3-6 gram: v3 not downloaded, copy v2 as-is.

Output: google-ngram-zh/{n}gram.json and {n}gram_tags.json
Then update algo/base.py _CORPUS_DIR to point here.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

V2 = Path('google-ngram-zh-2012')
V3 = Path('google-ngram-zh-2020')
OUT = Path('google-ngram-zh')


def load(path: Path) -> dict:
    if path.exists():
        with path.open('r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def merge_freqs(a: dict[str, float], b: dict[str, float]) -> dict[str, float]:
    result = dict(a)
    for k, v in b.items():
        result[k] = result.get(k, 0.0) + v
    return result


def merge_tags(a: dict[str, dict], b: dict[str, dict]) -> dict[str, dict]:
    """Union of tags; b (v3) takes precedence on key conflicts."""
    result: dict[str, dict] = {}
    all_keys = set(a) | set(b)
    for key in all_keys:
        entry_a = a.get(key, {})
        entry_b = b.get(key, {})
        merged = {**entry_a, **entry_b}  # b wins on conflict
        if merged:
            result[key] = merged
    return result


def dump(path: Path, data: dict) -> None:
    with path.open('w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False)


def main() -> None:
    OUT.mkdir(exist_ok=True)

    for n in range(1, 7):
        freq_v2 = load(V2 / f'{n}gram.json')
        freq_v3 = load(V3 / f'{n}gram.json')
        tag_v2  = load(V2 / f'{n}gram_tags.json')
        tag_v3  = load(V3 / f'{n}gram_tags.json')

        if not freq_v2 and not freq_v3:
            print(f'{n}gram: no data in either source, skipping')
            continue

        freq_merged = merge_freqs(freq_v2, freq_v3)
        tag_merged  = merge_tags(tag_v2, tag_v3)

        dump(OUT / f'{n}gram.json', freq_merged)
        if tag_merged:
            dump(OUT / f'{n}gram_tags.json', tag_merged)

        only_v2 = len(freq_v2) - len(set(freq_v2) & set(freq_v3))
        only_v3 = len(freq_v3) - len(set(freq_v2) & set(freq_v3))
        both    = len(set(freq_v2) & set(freq_v3))
        print(f'{n}gram: {len(freq_merged):>8,} total  '
              f'(both={both:,}  v2-only={only_v2:,}  v3-only={only_v3:,}  '
              f'tags={len(tag_merged):,})')

    # Copy stopwords
    sw = V2 / 'stopwords.txt'
    if sw.exists():
        shutil.copy(sw, OUT / 'stopwords.txt')
        print('copied stopwords.txt')

    print(f'\nDone → {OUT}')
    print('Update algo/base.py: _CORPUS_DIR = Path("google-ngram-zh")')


if __name__ == '__main__':
    main()
