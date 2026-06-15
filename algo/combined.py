"""Algo F: Combined — entity-filtered domain-boosted tri-prob + entropy selection.

Combines three existing algorithms:
  C (BodyBayes):    Phase 1 body unlock + adaptive tri-prob (alpha/beta/gamma) scoring.
  E (EntityDomain): Entity ngram filter + domain-match multiplier on title candidates.
  B (EntropyGuess): Entropy minimisation for final character selection.

Phase 1 — Passage Unlock: identical to C, with the same dynamic thresholds.

Phase 2 — Entity+Domain Tri-Prob + Entropy Selection:
  1. Build title candidates restricted to entity-tagged ngrams (E); apply a domain-match
     multiplier (DOMAIN_BOOST) when the ngram's domain matches the detected article domain.
  2. Compute char_title_prob (position-sensitive) from these boosted candidates.
  3. Compute char_body_prob and char_ngram_prob exactly as in C.
  4. Combine with C's adaptive weight schedule → char_posterior.
  5. Entropy selection: reweight each entity candidate by the posterior compatibility of
     its unknown-position chars, then pick the char that minimises expected Shannon
     entropy over this posterior-weighted distribution.  This replaces the plain
     frequency-argmax used in E and C, selecting the most informative next guess
     within the already-filtered, tri-prob-scored candidate set.
"""
from __future__ import annotations

import math
from collections import defaultdict

from algo.adaptive import BodyBayes, FUNCTION_WORDS, _phase1_thresholds

DOMAIN_BOOST = 2.5


class Combined(BodyBayes):
    """Entity-filtered domain-boosted tri-prob scoring + entropy-guided selection (C+E+B)."""

    DOMAIN_BOOST = DOMAIN_BOOST

    # ------------------------------------------------------------------ #
    # Entity + domain candidate building                                   #
    # ------------------------------------------------------------------ #

    def _get_boosted_entity_candidates(self, game) -> dict[str, float]:
        """Entity-filtered candidates with domain-match boost applied to frequencies."""
        title = game.puzzle.title
        candidates = self._get_entity_title_candidates(
            title, game.guessed_right, game.guessed_wrong
        )
        if not candidates:
            return candidates
        domain = self._detect_article_domain(game)
        if not domain:
            return candidates
        return {
            word: freq * (self.DOMAIN_BOOST if self._get_ngram_domain(word) == domain else 1.0)
            for word, freq in candidates.items()
        }

    def _get_title_prob_from_candidates(
        self,
        title: str,
        guessed_right: set[str],
        candidates: dict[str, float],
    ) -> dict[int, dict[str, float]]:
        """Position-sensitive title prob from an explicitly supplied candidate dict."""
        total = sum(candidates.values()) or 1.0
        char_title_prob: dict[int, dict[str, float]] = defaultdict(lambda: defaultdict(float))
        for pos in range(len(title)):
            if title[pos] not in guessed_right:
                for word, freq in candidates.items():
                    char_title_prob[pos][word[pos]] += freq / total
        return char_title_prob

    # ------------------------------------------------------------------ #
    # Entropy-guided final selection                                        #
    # ------------------------------------------------------------------ #

    def _entropy_select(
        self,
        char_posterior: dict[str, float],
        entity_candidates: dict[str, float],
        unknown_positions: set[int],
        guessed_combined: set[str],
    ) -> str | None:
        """Pick the char that minimises expected entropy over posterior-weighted entity candidates.

        Each entity candidate is reweighted by the sum of posterior scores for its
        unknown-position chars.  Entropy is computed via the identity
        H(subset) = log₂(Z) − (1/Z)·Σ f·log₂(f), precomputed in a single pass so
        per-char cost is O(|hit_words|) rather than O(|candidates|).
        Ties are broken by tri-prob posterior score.
        """
        if not char_posterior:
            return None
        if not entity_candidates:
            return max(char_posterior, key=char_posterior.get)

        # Posterior-weighted candidate distribution
        posterior_candidates: dict[str, float] = {}
        for word, base_freq in entity_candidates.items():
            compat = sum(
                char_posterior.get(word[pos], 0.0)
                for pos in unknown_positions
                if word[pos] not in guessed_combined
            )
            posterior_candidates[word] = base_freq * (compat + 1e-9)

        # Single pass: accumulate per-char freq and f·log₂(f) sums
        char_freq_sum: dict[str, float] = defaultdict(float)
        char_flogf_sum: dict[str, float] = defaultdict(float)
        total_freq = 0.0
        total_flogf = 0.0

        for word, freq in posterior_candidates.items():
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
            return max(char_posterior, key=char_posterior.get)

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
                and char_posterior.get(c, 0.0) > char_posterior.get(best_char or '', 0.0)
            ):
                best_expected_h = expected_h
                best_char = c

        return best_char

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
        min_body_hits, min_recognised = _phase1_thresholds(len(title))

        # Phase 1: function word unlock (same as C)
        if n_body_hits < min_body_hits and recognised < min_recognised:
            for fw in FUNCTION_WORDS:
                if fw not in guessed_combined:
                    print(f'Suggestion: {fw}  [phase-1: passage unlock]')
                    return fw

        # Phase 2: entity+domain tri-prob + entropy selection
        entity_candidates = self._get_boosted_entity_candidates(game)
        ngram_density = self._count_recognised_ngrams(game, body_text)
        alpha, beta, gamma = self._compute_weights(game, body_chars, ngram_density)
        has_body_hit = bool(game.guessed_right & body_chars)

        char_title_prob = self._get_title_prob_from_candidates(
            title, game.guessed_right, entity_candidates
        )
        char_body_prob = self._get_body_prob(game)
        char_ngram_prob = self._get_recognised_ngram_prob(game, body_text)

        char_posterior = self._combine_probs(
            char_title_prob, char_body_prob, char_ngram_prob,
            game, alpha, beta, gamma, has_body_hit,
        )

        unknown_positions = {
            pos for pos, char in enumerate(title)
            if char not in game.guessed_right
        }

        best_char = self._entropy_select(
            char_posterior, entity_candidates, unknown_positions, guessed_combined
        )

        if best_char is None:
            for char in sorted(self._freq[1], key=self._freq[1].get, reverse=True):
                if char not in guessed_combined and char not in self._stopwords:
                    print(f'Suggestion: {char}')
                    return char
            return None

        domain = self._detect_article_domain(game)
        label = f'  [domain={domain}]' if domain else ''
        print(f'Suggestion: {best_char}{label}')
        return best_char
