"""."""
from __future__ import annotations

from cli.game import BaikeGame, is_guessable_char, normalize_guess_char

MASK_CHAR = '■'


def render_game(game: BaikeGame) -> str:
    """Render game in terminal."""
    lines = [
        'Input one Chinese character, letter, or digit to guess. Type /quit to exit.',
        f'Date: {game.puzzle.date}',
        f'Guesses: {game.guess_count}',
        f'Found: {_format_sorted(game.guessed_right)}',
        f'Misses: {_format_sorted(game.guessed_wrong)}',
        '',
        _render_line(game.puzzle.title, game),
    ]

    if game.puzzle.author:
        lines.append(_render_line(game.puzzle.author, game))

    for paragraph in game.puzzle.paragraphs:
        lines.append('')
        for segment in paragraph:
            lines.append(_render_line(segment, game))

    return '\n'.join(lines)


def _render_line(text: str, game: BaikeGame) -> str:
    """Render lines of the game."""
    glyphs: list[str] = []
    for char in text:
        normalized = normalize_guess_char(char)
        if is_guessable_char(normalized):
            glyphs.append(char if normalized in game.guessed_right or game.correct else MASK_CHAR)
        else:
            glyphs.append(char)
    return ' '.join(glyphs)


def _format_sorted(chars: set[str]) -> str:
    """Format output."""
    if not chars:
        return '-'
    return ' '.join(sorted(chars))
