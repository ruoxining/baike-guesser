"""Algo E: Entity-Filtered Domain-Guided Search.

Baike article titles are almost always named entities (persons, places,
organisations, concepts).  This algorithm restricts the title candidate set
to ngrams tagged as entities, then boosts those whose domain matches the
inferred article domain.

Steps:
  1. Detect article domain by voting over 2-gram domain tags that are consistent
     with confirmed body chars.
  2. Filter title candidates to entity-tagged ngrams.  Falls back to the
     unconstrained candidate set if no entity ngrams survive.
  3. Apply a domain-match multiplier to entity candidates.
  4. Rank characters at unknown positions by weighted candidate frequency.
  5. Fall back to plain constraint-propagation unigram frequency if no candidates.
"""
from __future__ import annotations

from collections import defaultdict

from algo.base import BaseSuggest


class EntityDomain(BaseSuggest):
    """Entity-filtered + domain-boosted constraint propagation."""

    DOMAIN_BOOST = 2.5

    def suggest(self, game) -> str | None:
        title = game.puzzle.title
        guessed_combined = game.guessed_right | game.guessed_wrong
        domain = self._detect_article_domain(game)

        candidates = self._get_entity_title_candidates(
            title, game.guessed_right, game.guessed_wrong
        )

        if candidates:
            char_freq: dict[str, float] = defaultdict(float)
            for word, freq in candidates.items():
                ngram_domain = self._get_ngram_domain(word)
                boost = self.DOMAIN_BOOST if (domain and ngram_domain == domain) else 1.0
                for pos, char in enumerate(word):
                    if (
                        title[pos] not in game.guessed_right
                        and char not in guessed_combined
                        and char not in self._stopwords
                    ):
                        char_freq[char] += freq * boost

            if char_freq:
                best = max(char_freq, key=char_freq.get)
                label = f'  [domain={domain}]' if domain else ''
                print(f'Suggestion: {best}{label}')
                return best

        # Fallback: unigram frequency (same as ConstraintProp)
        for char in sorted(self._freq[1], key=self._freq[1].get, reverse=True):
            if char not in guessed_combined and char not in self._stopwords:
                print(f'Suggestion: {char}')
                return char

        return None
