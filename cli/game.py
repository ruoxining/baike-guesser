"""."""
from __future__ import annotations

from dataclasses import dataclass, field

from cli.client import BaikePuzzle


def is_cjk(char: str) -> bool:
    """Recognize CJK characters."""
    codepoint = ord(char)
    return (
        0x3400 <= codepoint <= 0x4DBF
        or 0x4E00 <= codepoint <= 0x9FFF
        or 0x20000 <= codepoint <= 0x2A6DF
        or 0x2A700 <= codepoint <= 0x2B73F
        or 0x2B740 <= codepoint <= 0x2B81F
        or 0x2B820 <= codepoint <= 0x2CEAF
        or 0x2CEB0 <= codepoint <= 0x2EBEF
        or 0xF900 <= codepoint <= 0xFAFF
    )


def _extract_cjk_chars(text: str) -> set[str]:
    """Get CJK characters."""
    return {char for char in text if is_cjk(char)}


@dataclass(slots=True)
class GuessResult:
    """Guess result class."""
    accepted_chars: list[str]
    repeated_chars: list[str]
    newly_correct: list[str]
    newly_wrong: list[str]
    correct: bool
    guess_count: int


@dataclass(slots=True)
class BaikeGame:
    """Class for overall Baike puzzle."""
    puzzle: BaikePuzzle
    guessed_right: set[str] = field(default_factory=set)
    guessed_wrong: set[str] = field(default_factory=set)
    guess_count: int = 0
    correct: bool = False
    all_chars: set[str] = field(init=False)
    title_chars: set[str] = field(init=False)

    def __post_init__(self) -> None:
        """Init function."""
        joined = self.puzzle.title
        if self.puzzle.author:
            joined += self.puzzle.author
        for paragraph in self.puzzle.paragraphs:
            joined += ''.join(paragraph)
        self.all_chars = _extract_cjk_chars(joined)
        self.title_chars = _extract_cjk_chars(self.puzzle.title)

    def guess(self, raw_text: str) -> GuessResult:
        """Guess procedure."""
        chars = _dedupe_guess(raw_text)
        if not chars:
            raise ValueError('请输入至少一个汉字')
        if len(chars) > 1:
            raise ValueError('每次最多输入 1 个汉字')

        accepted = [char for char in chars if char not in self.guessed_right and char not in self.guessed_wrong]
        repeated = [char for char in chars if char not in accepted]
        if not accepted:
            raise ValueError('这个字你猜过了')

        newly_correct: list[str] = []
        newly_wrong: list[str] = []
        for char in accepted:
            if char in self.all_chars:
                self.guessed_right.add(char)
                newly_correct.append(char)
            else:
                self.guessed_wrong.add(char)
                newly_wrong.append(char)

        self.guess_count += len(accepted)
        self.correct = self.title_chars.issubset(self.guessed_right)
        return GuessResult(
            accepted_chars=accepted,
            repeated_chars=repeated,
            newly_correct=newly_correct,
            newly_wrong=newly_wrong,
            correct=self.correct,
            guess_count=self.guess_count,
        )


def _dedupe_guess(raw_text: str) -> list[str]:
    """Get next batch of chars."""
    seen: set[str] = set()
    chars: list[str] = []
    for char in raw_text.strip():
        if not is_cjk(char) or char in seen:
            continue
        chars.append(char)
        seen.add(char)

    return chars
