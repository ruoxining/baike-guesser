"""Algo C: Body-Aware Bayesian Bridge.

Two-phase strategy that combines function-word passage unlocking with
game-state-driven Bayesian weight adjustment.

Phase 1 — Passage Unlock:
  Guess high-frequency grammatical words until the body is sufficiently
  unlocked (MIN_BODY_HITS correct guesses in body, or MIN_RECOGNISED recognised
  body ngrams).  This is a prerequisite for Phase 2's ngram signal to be useful.

Phase 2 — Adaptive Tri-Prob:
  Three signals combined with dynamically computed weights:
    alpha · title_ngram + beta · body_ngram + gamma · recognised_body_ngram

  Weight schedule (before renorm):
    alpha = clip(0.70 - 0.40·body_evidence + 0.20·title_coverage,  0.15, 0.80)
    gamma = clip(0.05 + 0.08·ngram_density,                         0.05, 0.50)
    beta  = max(0.05, 1 - alpha - gamma)

  Where body_evidence = |right ∩ body| / |right|, title_coverage = |right ∩ title| / |title|.
"""
from __future__ import annotations

from collections import defaultdict

from algo.base import BaseSuggest
from cli.game import is_guessable_char, normalize_guess_char

FUNCTION_WORDS: list[str] = [
    '的', '是', '在', '有', '年', '了', '被', '和', '也', '都',
    '不', '为', '以', '而', '其', '由', '于', '与', '月', '日',
    '后', '前', '此', '该', '将', '已', '曾', '可', '得', '使',
]

def _phase1_thresholds(title_len: int) -> tuple[int, int]:
    """Return (min_body_hits, min_recognised) exit thresholds for Phase 1.

    Short titles (≤3): entity candidates are few, function words rarely appear
    in 2-3 char names — exit Phase 1 after minimal evidence.
    Long titles (≥6): more unknown positions, body evidence is more valuable.
    """
    if title_len <= 3:
        return 1, 1
    if title_len <= 5:
        return 3, 2
    return 4, 3


class BodyBayes(BaseSuggest):
    """Function-word unlock (phase 1) + adaptive Bayesian tri-prob scoring (phase 2)."""

    # ------------------------------------------------------------------ #
    # Tri-prob scoring                                                      #
    # ------------------------------------------------------------------ #

    def _get_title_prob(
        self,
        title: str,
        guessed_right: set[str],
    ) -> dict[int, dict[str, float]]:
        """Position-sensitive probability from title ngram matching."""
        candidates = self._get_title_candidates(title, guessed_right, set())
        total = sum(candidates.values()) or 1
        char_title_prob: dict[int, dict[str, float]] = defaultdict(lambda: defaultdict(float))
        for pos in range(len(title)):
            if title[pos] not in guessed_right:
                for word, freq in candidates.items():
                    char_title_prob[pos][word[pos]] += freq / total
        return char_title_prob

    def _get_body_prob(self, game) -> dict[str, float]:
        """Position-insensitive probability from body ngrams."""
        char_count: dict[str, float] = defaultdict(float)
        total = 0.0
        guessed_right = game.guessed_right
        guessed_wrong = game.guessed_wrong

        for n in range(2, 7):
            if n not in self._freq:
                continue
            for ngram, freq in self._freq[n].items():
                ngram_set = set(ngram)
                if not guessed_right.issubset(ngram_set):
                    continue
                if guessed_wrong & ngram_set:
                    continue
                for char in ngram:
                    if char not in guessed_right and char not in guessed_wrong:
                        char_count[char] += freq
                        total += freq

        total = total or 1
        return {char: count / total for char, count in char_count.items()}

    def _get_recognised_ngram_prob(
        self,
        game,
        body_text: str,
    ) -> dict[int, dict[str, float]]:
        """Position-sensitive probs from body chunks matching corpus ngrams."""
        char_ngram_prob: dict[int, dict[str, float]] = defaultdict(lambda: defaultdict(float))
        guessed_right = game.guessed_right
        guessed_wrong = game.guessed_wrong
        chunks = self._chunk_body_by_punctuation(body_text)

        for chunk in chunks:
            n = len(chunk)
            if n < 1 or n > 6 or n not in self._freq:
                continue
            chunk_set = set(chunk)
            if not guessed_right.issubset(chunk_set):
                continue
            if guessed_wrong & chunk_set:
                continue
            mask = ''.join(c if c in guessed_right else '.' for c in chunk)
            regex = self._get_regex_pattern(mask)
            matching = {w: f for w, f in self._freq[n].items() if regex.match(w)}
            if not matching:
                continue
            total = sum(matching.values())
            for pos in range(n):
                if chunk[pos] not in guessed_right:
                    for word, freq in matching.items():
                        char_ngram_prob[pos][word[pos]] += freq / total

        return char_ngram_prob

    def _combine_probs(
        self,
        char_title_prob,
        char_body_prob,
        char_ngram_prob,
        game,
        alpha: float,
        beta: float,
        gamma: float,
        has_body_hit: bool,
    ) -> dict[str, float]:
        assert abs(alpha + beta + gamma - 1) < 1e-9

        char_posterior: dict[str, list] = defaultdict(lambda: [0.0, 0])
        guessed_combined = game.guessed_right | game.guessed_wrong

        total_weight = alpha + beta
        alpha_reweight = alpha / total_weight if total_weight > 0 else 0.5
        beta_reweight = beta / total_weight if total_weight > 0 else 0.5

        phase_alpha = alpha_reweight if has_body_hit else 1.0
        phase_beta = beta_reweight if has_body_hit else 0.0

        for pos, pos_probs in char_title_prob.items():
            for char, prob_title in pos_probs.items():
                if char in self._stopwords or char in guessed_combined:
                    continue
                prob_text = char_body_prob.get(char, 0.0)
                prob_ngram = char_ngram_prob.get(pos, {}).get(char, 0.0)
                if prob_ngram > 0:
                    posterior = alpha * prob_title + beta * prob_text + gamma * prob_ngram
                else:
                    posterior = phase_alpha * prob_title + phase_beta * prob_text
                char_posterior[char][0] += posterior
                char_posterior[char][1] += 1

        for pos, pos_probs in char_ngram_prob.items():
            for char, prob_ngram in pos_probs.items():
                if char in self._stopwords or char in guessed_combined:
                    continue
                if char not in char_posterior:
                    prob_title = char_title_prob.get(pos, {}).get(char, 0.0)
                    prob_text = char_body_prob.get(char, 0.0)
                    posterior = alpha * prob_title + beta * prob_text + gamma * prob_ngram
                    char_posterior[char][0] += posterior
                    char_posterior[char][1] += 1

        return {char: total / count for char, (total, count) in char_posterior.items()}

    # ------------------------------------------------------------------ #
    # Adaptive weight schedule                                              #
    # ------------------------------------------------------------------ #

    def _compute_weights(
        self,
        game,
        body_chars: set[str],
        ngram_density: int,
    ) -> tuple[float, float, float]:
        n_right = len(game.guessed_right)
        if n_right == 0:
            return 0.70, 0.25, 0.05

        body_evidence = len(game.guessed_right & body_chars) / n_right
        title_coverage = len(game.guessed_right & game.title_chars) / max(len(game.title_chars), 1)

        alpha_raw = 0.70 - 0.40 * body_evidence + 0.20 * title_coverage
        alpha = max(0.15, min(0.80, alpha_raw))
        gamma = max(0.05, min(0.50, 0.05 + 0.08 * ngram_density))
        beta = max(0.05, 1.0 - alpha - gamma)

        total = alpha + beta + gamma
        return alpha / total, beta / total, gamma / total

    # ------------------------------------------------------------------ #
    # Main suggest                                                          #
    # ------------------------------------------------------------------ #

    def suggest(self, game) -> str | None:
        title = game.puzzle.title
        body_text = self._get_body_text(game)
        body_chars = self._get_body_chars(game)
        guessed_combined = game.guessed_right | game.guessed_wrong

        n_body_hits = len(game.guessed_right & body_chars)
        recognised = self._count_recognised_ngrams(game, body_text)

        # Phase 1: guess function words until body is sufficiently unlocked
        min_body_hits, min_recognised = _phase1_thresholds(len(title))
        if n_body_hits < min_body_hits and recognised < min_recognised:
            for fw in FUNCTION_WORDS:
                if fw not in guessed_combined:
                    print(f'Suggestion: {fw}  [phase-1: passage unlock]')
                    return fw

        # Phase 2: adaptive Bayesian tri-prob scoring
        ngram_density = self._count_recognised_ngrams(game, body_text)
        alpha, beta, gamma = self._compute_weights(game, body_chars, ngram_density)
        has_body_hit = bool(game.guessed_right & body_chars)

        char_title_prob = self._get_title_prob(title, game.guessed_right)
        char_body_prob = self._get_body_prob(game)
        char_ngram_prob = self._get_recognised_ngram_prob(game, body_text)

        char_posterior = self._combine_probs(
            char_title_prob, char_body_prob, char_ngram_prob,
            game, alpha, beta, gamma, has_body_hit,
        )

        best_char = max(char_posterior, default=None, key=char_posterior.get)
        print(f'Suggestion: {best_char}')
        return best_char
