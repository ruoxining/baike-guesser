"""Command-line interface for guess baike puzzle."""
from __future__ import annotations

import argparse
import json
import sys

from algo.adaptive import BodyBayes
from algo.combined import Combined
from algo.constraint import ConstraintProp
from algo.embedding import EmbeddingGuess
from algo.entity import EntityDomain
from algo.entropy import EntropyGuess
from cli.client import (BaikePuzzle, fetch_html, get_baike_puzzle,
                        get_latest_daily_date)
from cli.game import BaikeGame
from cli.render import render_game

_ALGO_MENU = [
    ('A', 'ConstraintProp', ConstraintProp),
    ('B', 'EntropyGuess',   EntropyGuess),
    ('C', 'BodyBayes',      BodyBayes),
    ('D', 'EmbeddingGuess', EmbeddingGuess),
    ('E', 'EntityDomain',   EntityDomain),
    ('F', 'Combined',       Combined),
]

_ALGO_HELP = {
    'A': (
        'ConstraintProp (baseline)\n'
        '  Wordle-style hard constraint propagation. Maintains the set of all corpus\n'
        '  ngrams consistent with every piece of feedback, then picks the highest-\n'
        '  frequency character at still-unknown positions. Fastest; clean baseline.'
    ),
    'B': (
        'EntropyGuess\n'
        '  Information-theoretic search. Picks the character that maximises expected\n'
        '  Shannon entropy reduction over the title candidate set — trades short-term\n'
        '  hit probability for faster long-term convergence.'
    ),
    'C': (
        'BodyBayes\n'
        '  Two-phase body-aware Bayesian approach. Phase 1 guesses function words\n'
        '  (的/是/在/有/年…) to unlock passage context. Phase 2 combines title-ngram,\n'
        '  body-ngram, and recognised-body signals with adaptive weights. Best for\n'
        '  long passages.'
    ),
    'D': (
        'EmbeddingGuess\n'
        '  Distributional semantic similarity built from ngram co-occurrence. Slow\n'
        '  init (~seconds). Body chars confirmed so far form a context vector;\n'
        '  candidates are scored by semantic proximity + domain boost. Good for\n'
        '  rare proper nouns.'
    ),
    'E': (
        'EntityDomain\n'
        '  Entity filtering + domain boosting. Restricts title candidates to named-\n'
        '  entity ngrams and applies a 2.5× boost to those matching the detected\n'
        '  article domain (geography / history / science…). Highest precision when\n'
        '  entity coverage is good.'
    ),
    'F': (
        'Combined\n'
        '  Combines E (entity/domain filter), C (adaptive tri-prob body evidence),\n'
        '  and B (entropy-guided selection) into one pipeline. Highest expected\n'
        '  accuracy; roughly the same speed as C on most titles.'
    ),
}

_ALGO_BY_NAME = {
    'constraint':     ConstraintProp,
    'entropy':        EntropyGuess,
    'body-bayes':     BodyBayes,
    'embedding':      EmbeddingGuess,
    'entity':         EntityDomain,
    'combined':       Combined,
}


def _select_algorithm():
    """Show algorithm menu and return instantiated algorithm."""
    print('Select algorithm:')
    for key, name, _ in _ALGO_MENU:
        print(f'  [{key}] {name}')
    print('  [Q] Quit')
    print('  Type ?A–?F for a description of any algorithm.')
    print()

    valid = {entry[0].upper(): entry for entry in _ALGO_MENU}
    while True:
        try:
            raw = input('Enter A–F (or Q to quit): ').strip()
        except (EOFError, KeyboardInterrupt):
            raise KeyboardInterrupt

        if not raw:
            continue

        upper = raw.upper()

        if upper.startswith('?'):
            key = upper[1:].strip()
            if key in _ALGO_HELP:
                print()
                print(_ALGO_HELP[key])
                print()
            else:
                keys = ', '.join(k for k, *_ in _ALGO_MENU)
                print(f'  No help for "{raw[1:]}". Try ?A through ?F ({keys}).')
            continue

        key = upper[0] if upper else ''
        if key in valid:
            _, _, cls = valid[key]
            print(f'Loading {cls.__name__}...')
            return cls()
        if key in {'Q', '\x03', '\x04'} or not key:
            raise KeyboardInterrupt
        print(f'  Unknown option "{raw}". Enter A–F, ?A–?F for help, or Q to quit.')


def main() -> int:
    """Main function."""
    parser = argparse.ArgumentParser(description='Terminal helper for xiaoce.fun/baike')
    parser.add_argument('--date', help='Puzzle date in YYYYMMDD format')
    parser.add_argument('--sub-type', help='Optional subType such as genshin/geography/history/mc')
    parser.add_argument('--infinity', action='store_true', help='Use the infinity puzzle endpoint')
    parser.add_argument('--author', help='Author value for infinity mode')
    parser.add_argument('--show-html', action='store_true', help='Print parsed HTML page metadata before the game')
    parser.add_argument('--from-file', metavar='FILE', help='Load puzzle from a saved JSON file instead of fetching')
    parser.add_argument(
        '--algo',
        choices=list(_ALGO_BY_NAME),
        metavar='ALGO',
        help=f'Skip menu and use this algorithm directly ({"|".join(_ALGO_BY_NAME)})',
    )
    args = parser.parse_args()

    if args.algo:
        suggest = _ALGO_BY_NAME[args.algo]()
    else:
        try:
            suggest = _select_algorithm()
        except KeyboardInterrupt:
            print()
            return 0
    print()

    try:
        if args.from_file:
            with open(args.from_file) as f:
                d = json.load(f)
            puzzle = BaikePuzzle(
                title=d['title'], author=d.get('author'),
                paragraphs=d['paragraphs'], date=d['date'], raw_response={},
            )
            page_info = None
        else:
            page_info = fetch_html()
            date = args.date or get_latest_daily_date()
            puzzle = get_baike_puzzle(
                date=None if args.infinity else date,
                sub_type=args.sub_type,
                infinity=args.infinity,
                author=args.author,
            )
    except Exception as exc:
        print(f'Failed to fetch puzzle: {exc}', file=sys.stderr)
        return 1

    if args.show_html and page_info is not None:
        print(f'Page title: {page_info.title}')
        if page_info.module_scripts:
            print('Module scripts:')
            for script in page_info.module_scripts:
                print(f'  {script}')
        if page_info.stylesheets:
            print('Stylesheets:')
            for stylesheet in page_info.stylesheets:
                print(f'  {stylesheet}')
        print()

    game = BaikeGame(puzzle)
    print(render_game(game))
    suggest.suggest(game)

    while not game.correct:
        try:
            raw = input('> ').strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not raw:
            continue
        if raw in {'/quit', '/exit'}:
            break

        try:
            result = game.guess(raw)
        except ValueError as exc:
            print(exc)
            continue

        print(render_game(game))
        suggest.suggest(game)

        if result.newly_wrong:
            print(f"Not in puzzle: {' '.join(result.newly_wrong)}")
        if result.repeated_chars:
            print(f"Already guessed: {' '.join(result.repeated_chars)}")
        if game.correct:
            print(f'Solved in {game.guess_count} guesses.')
        print()

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
