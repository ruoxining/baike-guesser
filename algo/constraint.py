"""Algo A: Constraint Propagation — Wordle-style candidate pruning (baseline).

Maintains the set of corpus ngrams consistent with all positional hits and misses.
At each step, selects the character most frequent across surviving candidates at
still-unknown positions.

Falls back to unigram frequency when the title exceeds 6 chars (outside corpus
range) or when no candidates survive pruning.
"""
from __future__ import annotations

from collections import defaultdict

from algo.base import BaseSuggest


class ConstraintProp(BaseSuggest):
    """Baseline: candidate-set frequency ranking with hard constraint propagation."""

    def suggest(self, game) -> str | None:
        title = game.puzzle.title
        guessed_combined = game.guessed_right | game.guessed_wrong

        candidates = self._get_title_candidates(title, game.guessed_right, game.guessed_wrong)

        if candidates:
            char_freq: dict[str, float] = defaultdict(float)
            for word, freq in candidates.items():
                for pos, char in enumerate(word):
                    if (
                        title[pos] not in game.guessed_right
                        and char not in guessed_combined
                        and char not in self._stopwords
                    ):
                        char_freq[char] += freq

            if char_freq:
                best = max(char_freq, key=char_freq.get)
                print(f'Suggestion: {best}')
                return best

        # Fallback: most frequent unguessed unigram
        for char in sorted(self._freq[1], key=self._freq[1].get, reverse=True):
            if char not in guessed_combined and char not in self._stopwords:
                print(f'Suggestion: {char}')
                return char

        return None
