"""Algo B: Entropy-Guided Search.

At each step, picks the character that maximises the expected reduction in
Shannon entropy over the remaining title-candidate set.

For every unguessed candidate character c:
  - S_hit   = candidates in which c occupies at least one unknown position
  - S_miss  = candidates - S_hit
  - p_hit   = Σfreq(S_hit) / Σfreq(all)
  - E[H|c]  = p_hit · H(S_hit) + (1−p_hit) · H(S_miss)

We choose argmin_c E[H|c].  Ties broken by corpus frequency.

Falls back to highest-frequency unguessed unigram when the title length exceeds
the ngram corpus range (>6) or the candidate set is empty.

Implementation note — precomputed f·log₂(f):
  H(subset) = log₂(Z) − (1/Z)·Σ_{i∈subset} f_i·log₂(f_i)
  Precomputing f_i·log₂(f_i) for every candidate lets us compute entropy for
  any hit/miss partition in O(|hit|) rather than O(|candidates|), reducing the
  overall complexity from O(|chars|×|candidates|×|unknown_pos|) to
  O(|candidates|×|unknown_pos|).
"""
from __future__ import annotations

import math
from collections import defaultdict

from algo.base import BaseSuggest


class EntropyGuess(BaseSuggest):
    """Pick the guess that most reduces entropy over title candidates."""

    def suggest(self, game) -> str | None:
        title = game.puzzle.title
        guessed_combined = game.guessed_right | game.guessed_wrong

        candidates = self._get_title_candidates(title, game.guessed_right, game.guessed_wrong)

        if not candidates:
            for char in sorted(self._freq[1], key=self._freq[1].get, reverse=True):
                if char not in guessed_combined and char not in self._stopwords:
                    print(f'Suggestion: {char}')
                    return char
            return None

        unknown_positions = {
            pos for pos, char in enumerate(title)
            if char not in game.guessed_right
        }

        # Single pass over candidates: accumulate per-char freq and f·log₂(f) sums.
        # For each candidate char c, char_freq_sum[c] = Σ freq for words where c
        # appears at some unknown position (i.e. the hit-partition total).
        char_freq_sum: dict[str, float] = defaultdict(float)
        char_flogf_sum: dict[str, float] = defaultdict(float)
        total_freq = 0.0
        total_flogf = 0.0

        for word, freq in candidates.items():
            total_freq += freq
            f_lf = freq * math.log2(freq) if freq > 0 else 0.0
            total_flogf += f_lf
            seen: set[str] = set()
            for pos in unknown_positions:
                c = word[pos]
                if c in seen or c in guessed_combined or c in self._stopwords:
                    continue
                seen.add(c)
                char_freq_sum[c] += freq
                char_flogf_sum[c] += f_lf

        candidate_chars = set(char_freq_sum)
        if not candidate_chars:
            return None

        best_char: str | None = None
        best_expected_h = float('inf')

        for c in candidate_chars:
            hit_total = char_freq_sum[c]
            miss_total = total_freq - hit_total
            hit_flogf = char_flogf_sum[c]
            miss_flogf = total_flogf - hit_flogf

            p_hit = hit_total / total_freq
            p_miss = 1.0 - p_hit
            h_hit = (math.log2(hit_total) - hit_flogf / hit_total) if hit_total > 0 else 0.0
            h_miss = (math.log2(miss_total) - miss_flogf / miss_total) if miss_total > 0 else 0.0
            expected_h = p_hit * h_hit + p_miss * h_miss

            if expected_h < best_expected_h or (
                expected_h == best_expected_h
                and self._freq[1].get(c, 0) > self._freq[1].get(best_char or '', 0)
            ):
                best_expected_h = expected_h
                best_char = c

        print(f'Suggestion: {best_char}')
        return best_char
