"""Command-line interface for guess baike puzzle."""
from __future__ import annotations

import argparse
import json
import sys

from algo.constraint import ConstraintProp
from algo.entropy import EntropyGuess
from algo.adaptive import BodyBayes
from algo.embedding import EmbeddingGuess
from algo.entity import EntityDomain
from algo.combined import Combined
from cli.client import BaikePuzzle, fetch_html, get_baike_puzzle, get_latest_daily_date
from cli.game import BaikeGame
from cli.render import render_game

_ALGO_MENU = [
    ('A', 'ConstraintProp  (baseline: Wordle-style hard constraint propagation)', ConstraintProp),
    ('B', 'EntropyGuess    (information-theoretic: max entropy reduction)', EntropyGuess),
    ('C', 'BodyBayes       (function-word unlock + adaptive Bayesian tri-prob)', BodyBayes),
    ('D', 'EmbeddingGuess  (ngram co-occurrence + domain-aware embeddings)', EmbeddingGuess),
    ('E', 'EntityDomain    (entity-filtered + domain-boosted candidates)', EntityDomain),
    ('F', 'Combined        (entity+domain tri-prob + entropy-guided selection)', Combined),
]

_ALGO_BY_NAME = {
    'constraint':     ConstraintProp,
    'entropy':        EntropyGuess,
    'body-bayes':     BodyBayes,
    'embedding':      EmbeddingGuess,
    'entity':         EntityDomain,
    'combined':       Combined,
}


def _read_single_key() -> str:
    """Read one keypress from stdin without requiring Enter."""
    try:
        import tty
        import termios
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            return sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)
            termios.tcflush(fd, termios.TCIFLUSH)
    except Exception:
        # stdin is not a real TTY (pipe, IDE, etc.) — fall back to line input
        line = sys.stdin.readline()
        return line.strip()[:1] if line.strip() else '\x04'


def _select_algorithm():
    """Show algorithm menu and return instantiated algorithm."""
    print('Select algorithm:')
    for key, desc, _ in _ALGO_MENU:
        print(f'  [{key}] {desc}')
    print('  [Q] Quit')
    print()

    valid = {entry[0].upper(): entry for entry in _ALGO_MENU}
    while True:
        sys.stdout.write('Press A–F (or Q to quit): ')
        sys.stdout.flush()
        ch = _read_single_key().upper()
        if ch:
            print(ch)
        if ch in valid:
            _, _, cls = valid[ch]
            print(f'Loading {cls.__name__}...')
            return cls()
        if ch in {'\x03', '\x04', 'Q', ''}:
            raise KeyboardInterrupt
        # invalid key — loop silently


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
