"""Command-line interface for guess baike puzzle."""
from __future__ import annotations

import argparse
import sys

from algo.suggest import Suggest
from cli.client import fetch_html, get_baike_puzzle, get_latest_daily_date
from cli.game import BaikeGame
from cli.render import render_game


def main() -> int:
    """Main function."""
    parser = argparse.ArgumentParser(description='Terminal helper for xiaoce.fun/baike')
    parser.add_argument('--date', help='Puzzle date in YYYYMMDD format')
    parser.add_argument('--sub-type', help='Optional subType such as genshin/geography/history/mc')
    parser.add_argument('--infinity', action='store_true', help='Use the infinity puzzle endpoint')
    parser.add_argument('--author', help='Author value for infinity mode')
    parser.add_argument('--show-html', action='store_true', help='Print parsed HTML page metadata before the game')
    args = parser.parse_args()

    try:
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

    if args.show_html:
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

    # TODO: print suggestion of game
    suggest = Suggest()
    suggest.suggest(game)

    print('Input one Chinese character, letter, or digit to guess. Type /quit to exit.')

    while not game.correct:
        try:
            raw = input('> ').strip()
        except EOFError:
            print()
            break
        except KeyboardInterrupt:
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
