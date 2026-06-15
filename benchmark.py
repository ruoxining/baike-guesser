"""Benchmark all suggestion algorithms against saved puzzles.

For each puzzle in puzzles/, each algorithm plays the game autonomously
(suggest → guess → repeat) and we record the number of guesses needed.

Usage:
    python3 benchmark.py                    # all puzzles, all algorithms
    python3 benchmark.py --algos baseline constraint entropy
    python3 benchmark.py --max-guesses 60
    python3 benchmark.py --puzzle puzzles/20260604.json

Output: a table printed to stdout and results saved to benchmark_results.json.
"""
from __future__ import annotations

import argparse
import io
import json
import os
import sys
from contextlib import redirect_stdout
from dataclasses import dataclass

from cli.client import BaikePuzzle
from cli.game import BaikeGame

MAX_GUESSES_DEFAULT = 80

ALGO_REGISTRY: dict[str, type] = {}

def _register():
    from algo.constraint import ConstraintProp
    from algo.entropy import EntropyGuess
    from algo.adaptive import BodyBayes
    from algo.embedding import EmbeddingGuess
    from algo.entity import EntityDomain
    from algo.combined import Combined
    ALGO_REGISTRY.update({
        'constraint': ConstraintProp,
        'entropy':    EntropyGuess,
        'body-bayes': BodyBayes,
        'embedding':  EmbeddingGuess,
        'entity':     EntityDomain,
        'combined':   Combined,
    })


@dataclass
class RunResult:
    algo: str
    puzzle_date: str
    puzzle_file: str
    solved: bool
    guesses: int
    title_len: int


def _load_puzzle(path: str) -> BaikePuzzle:
    with open(path, 'r', encoding='utf-8') as f:
        d = json.load(f)
    return BaikePuzzle(
        title=d['title'],
        author=d.get('author'),
        paragraphs=d['paragraphs'],
        date=d['date'],
        raw_response={},
    )


def _run_once(solver, puzzle: BaikePuzzle, max_guesses: int) -> tuple[bool, int]:
    """Simulate one full game. Returns (solved, guess_count)."""
    game = BaikeGame(puzzle)
    buf = io.StringIO()
    for _ in range(max_guesses):
        if game.correct:
            break
        with redirect_stdout(buf):
            char = solver.suggest(game)
        if char is None:
            break
        try:
            game.guess(char)
        except ValueError:
            # already guessed — solver is stuck
            break
    return game.correct, game.guess_count


def _fmt(val: float | None, width: int = 7) -> str:
    if val is None:
        return ' ' * width
    return f'{val:>{width}.2f}'


def benchmark(
    puzzle_paths: list[str],
    algo_names: list[str],
    max_guesses: int,
) -> list[RunResult]:
    _register()

    print('Initialising solvers...', flush=True)
    solvers: dict[str, object] = {}
    for name in algo_names:
        print(f'  {name}...', end=' ', flush=True)
        solvers[name] = ALGO_REGISTRY[name]()
        print('OK')

    results: list[RunResult] = []

    for path in puzzle_paths:
        puzzle = _load_puzzle(path)
        fname = os.path.basename(path)
        print(f'\nPuzzle: {fname}  (title len={len(puzzle.title)})')

        for name in algo_names:
            solver = solvers[name]
            solved, guesses = _run_once(solver, puzzle, max_guesses)
            status = f'{guesses:3d} guesses' if solved else f'FAILED (>{max_guesses})'
            print(f'  {name:<14} {status}')
            results.append(RunResult(
                algo=name,
                puzzle_date=puzzle.date,
                puzzle_file=fname,
                solved=solved,
                guesses=guesses,
                title_len=len(puzzle.title),
            ))

    return results


def print_summary(results: list[RunResult], algo_names: list[str]) -> None:
    puzzle_files = sorted({r.puzzle_file for r in results})
    n_puzzles = len(puzzle_files)

    print('\n' + '=' * 72)
    print('SUMMARY')
    print('=' * 72)

    header = f'{"Algorithm":<15}' + ''.join(f'{p[:10]:>12}' for p in puzzle_files) + f'{"avg":>8}  {"solved":>7}'
    print(header)
    print('-' * len(header))

    for name in algo_names:
        algo_results = [r for r in results if r.algo == name]
        per_puzzle = {r.puzzle_file: r for r in algo_results}
        cols = ''
        guess_counts = []
        solved_count = 0
        for pf in puzzle_files:
            r = per_puzzle.get(pf)
            if r and r.solved:
                cols += f'{r.guesses:>12}'
                guess_counts.append(r.guesses)
                solved_count += 1
            elif r:
                cols += f'{"DNF":>12}'
            else:
                cols += f'{"—":>12}'
        avg = sum(guess_counts) / len(guess_counts) if guess_counts else None
        print(f'{name:<15}{cols}{_fmt(avg)}  {solved_count:>4}/{n_puzzles}')

    print('=' * 72)


def save_results(results: list[RunResult], path: str = 'benchmark_results.json') -> None:
    data = [
        {
            'algo': r.algo,
            'puzzle_date': r.puzzle_date,
            'puzzle_file': r.puzzle_file,
            'solved': r.solved,
            'guesses': r.guesses,
            'title_len': r.title_len,
        }
        for r in results
    ]
    # Merge with existing results if file exists
    existing = []
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            existing = json.load(f)
        # Deduplicate by (algo, puzzle_file)
        existing_keys = {(d['algo'], d['puzzle_file']) for d in data}
        existing = [d for d in existing if (d['algo'], d['puzzle_file']) not in existing_keys]

    with open(path, 'w', encoding='utf-8') as f:
        json.dump(existing + data, f, ensure_ascii=False, indent=2)
    print(f'\nResults saved to {path}')


def main() -> int:
    parser = argparse.ArgumentParser(description='Benchmark Baike solver algorithms')
    parser.add_argument('--puzzle', nargs='+', help='Specific puzzle JSON file(s)')
    parser.add_argument(
        '--algos', nargs='+',
        choices=['constraint', 'entropy', 'body-bayes', 'embedding', 'entity', 'combined'],
        default=['constraint', 'entropy', 'body-bayes', 'embedding', 'entity', 'combined'],
        help='Algorithms to benchmark',
    )
    parser.add_argument('--max-guesses', type=int, default=MAX_GUESSES_DEFAULT)
    parser.add_argument('--no-save', action='store_true', help='Do not write benchmark_results.json')
    args = parser.parse_args()

    if args.puzzle:
        puzzle_paths = args.puzzle
    else:
        if not os.path.isdir('puzzles'):
            print('No puzzles/ directory found. Run record_puzzle.py first.', file=sys.stderr)
            return 1
        puzzle_paths = sorted(
            os.path.join('puzzles', f)
            for f in os.listdir('puzzles')
            if f.endswith('.json')
        )
        if not puzzle_paths:
            print('No puzzle files found in puzzles/. Run record_puzzle.py first.', file=sys.stderr)
            return 1

    print(f'Puzzles   : {len(puzzle_paths)}')
    print(f'Algorithms: {", ".join(args.algos)}')
    print(f'Max guesses: {args.max_guesses}')

    results = benchmark(puzzle_paths, args.algos, args.max_guesses)
    print_summary(results, args.algos)

    if not args.no_save:
        save_results(results)

    return 0


if __name__ == '__main__':
    raise SystemExit(main())

