#!/usr/bin/env python3
"""Fetch a Baike puzzle and save it to puzzles/<date>[_subtype].json."""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

from cli.client import get_baike_puzzle, get_latest_daily_date


def main() -> int:
    parser = argparse.ArgumentParser(description='Save a Baike puzzle to disk')
    parser.add_argument('--date', help='Puzzle date YYYYMMDD (default: today)')
    parser.add_argument('--sub-type', help='Puzzle sub-type, e.g. history / geography')
    args = parser.parse_args()

    date = args.date or get_latest_daily_date()
    sub_type = args.sub_type

    tag = date + (f'_{sub_type}' if sub_type else '')
    out = pathlib.Path('puzzles') / f'{tag}.json'
    out.parent.mkdir(exist_ok=True)

    if out.exists():
        print(f'Already saved: {out}')
        return 0

    try:
        puzzle = get_baike_puzzle(date=date, sub_type=sub_type)
    except Exception as exc:
        print(f'Failed to fetch puzzle: {exc}', file=sys.stderr)
        return 1

    out.write_text(
        json.dumps(
            {
                'date': puzzle.date,
                'title': puzzle.title,
                'author': puzzle.author,
                'paragraphs': puzzle.paragraphs,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    print(f'Saved: {out}  ({len(puzzle.title)} chars, {len(puzzle.paragraphs)} paragraphs)')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
