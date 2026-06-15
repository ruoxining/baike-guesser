"""Algo D: Domain-Aware Embedding Similarity.

Builds a lightweight distributional character embedding from the Google Ngram
corpus — no external model required.  For each character c, its embedding vector
records co-occurrence counts with every other character across all 2–5 grams,
weighted by corpus frequency.  Vectors are L2-normalised so cosine similarity
reduces to a dot product.

At suggestion time:
  1. Detect article domain via 2-gram tag voting on confirmed body chars.
  2. Build a context vector as the (optionally domain-boosted) mean of embeddings
     for chars confirmed in the body.  This approximates the article's topic.
  3. Score every candidate char:
       score = w_freq · freq_score + w_sem · sem_score + w_uni · log_prior
     where sem_score is cosine similarity to the context vector, and freq_score
     comes from corpus-frequency-weighted counting over title candidates.
  4. When no body context is available (early game), degrade to:
       score = w_freq · freq_score + w_uni · log_prior

Initialisation builds the co-occurrence matrix once; subsequent calls are fast.
"""
from __future__ import annotations

import math
from collections import defaultdict

from algo.base import BaseSuggest


class EmbeddingGuess(BaseSuggest):
    """Frequency + distributional semantic similarity over title candidates."""

    # Scoring weights (context available / no context)
    W_FREQ_CTX = 0.50
    W_SEM_CTX = 0.35
    W_UNI_CTX = 0.15
    W_FREQ_NOCTX = 0.80
    W_UNI_NOCTX = 0.20

    def __init__(self) -> None:
        super().__init__()
        self._build_char_vectors()

    def _build_char_vectors(self) -> None:
        """Build L2-normalised co-occurrence vectors from 2–5 grams."""
        cooccur: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
        for n in range(2, 6):
            if n not in self._freq:
                continue
            for ngram, freq in self._freq[n].items():
                chars = list(ngram)
                for i, c1 in enumerate(chars):
                    for j, c2 in enumerate(chars):
                        if i != j:
                            cooccur[c1][c2] += freq

        self._char_vectors: dict[str, dict[str, float]] = {}
        for char, vec in cooccur.items():
            norm = math.sqrt(sum(v * v for v in vec.values()))
            if norm > 0:
                self._char_vectors[char] = {k: v / norm for k, v in vec.items()}

    def _cosine(self, v1: dict[str, float], v2: dict[str, float]) -> float:
        """Dot product of two already-L2-normalised sparse vectors."""
        shared = set(v1) & set(v2)
        return sum(v1[k] * v2[k] for k in shared)

    def _mean_vector(self, chars: set[str]) -> dict[str, float]:
        """Mean of embedding vectors, then re-L2-normalised."""
        vecs = [self._char_vectors[c] for c in chars if c in self._char_vectors]
        if not vecs:
            return {}
        result: dict[str, float] = defaultdict(float)
        for v in vecs:
            for k, val in v.items():
                result[k] += val
        norm = math.sqrt(sum(x * x for x in result.values()))
        if norm > 0:
            return {k: x / norm for k, x in result.items()}
        return dict(result)

    def _log_prior(self, char: str) -> float:
        """Normalised log unigram frequency in [0, 1]."""
        raw = math.log(self._freq[1].get(char, 1e-12) + 1e-12)
        return max(0.0, (raw + 28.0) / 28.0)

    def _build_context_vector(
        self,
        context_chars: set[str],
        article_domain: str | None,
    ) -> dict[str, float]:
        """Build domain-boosted context vector from confirmed body chars."""
        if not article_domain or not context_chars:
            return self._mean_vector(context_chars)

        weighted: dict[str, float] = {}
        for c in context_chars:
            boost = 1.0
            for ngram, tag in self._tags.get(2, {}).items():
                if c in ngram and tag.get('domain') == article_domain:
                    boost = 2.0
                    break
            weighted[c] = boost

        vecs = [
            {k: v * weighted[c] for k, v in self._char_vectors[c].items()}
            for c in context_chars if c in self._char_vectors
        ]
        if not vecs:
            return {}
        result: dict[str, float] = defaultdict(float)
        for v in vecs:
            for k, val in v.items():
                result[k] += val
        norm = math.sqrt(sum(x * x for x in result.values()))
        return {k: x / norm for k, x in result.items()} if norm > 0 else {}

    def suggest(self, game) -> str | None:
        title = game.puzzle.title
        guessed_combined = game.guessed_right | game.guessed_wrong

        candidates = self._get_title_candidates(title, game.guessed_right, game.guessed_wrong)
        unknown_positions = {
            pos for pos, char in enumerate(title) if char not in game.guessed_right
        }

        char_freq: dict[str, float] = defaultdict(float)
        total_freq = sum(candidates.values()) or 1.0
        for word, freq in candidates.items():
            for pos in unknown_positions:
                char = word[pos]
                if char not in guessed_combined and char not in self._stopwords:
                    char_freq[char] += freq / total_freq

        body_chars = self._get_body_chars(game)
        context_chars = game.guessed_right & body_chars
        article_domain = self._detect_article_domain(game)
        context_vector = self._build_context_vector(context_chars, article_domain)
        has_context = bool(context_vector)

        # Supplement sparse candidate chars with top unigrams
        candidate_chars: set[str] = set(char_freq.keys())
        if len(candidate_chars) < 30:
            for char in sorted(self._freq[1], key=self._freq[1].get, reverse=True)[:300]:
                if char not in guessed_combined and char not in self._stopwords:
                    candidate_chars.add(char)

        char_scores: dict[str, float] = {}
        for char in candidate_chars:
            if char in guessed_combined or char in self._stopwords:
                continue

            freq_score = char_freq.get(char, 0.0)
            log_prior = self._log_prior(char)

            if has_context and char in self._char_vectors:
                sem_score = self._cosine(context_vector, self._char_vectors[char])
                domain_bonus = 0.05 if (
                    article_domain and
                    any(article_domain == tag.get('domain')
                        for ngram, tag in self._tags.get(2, {}).items()
                        if char in ngram)
                ) else 0.0
                score = (
                    self.W_FREQ_CTX * freq_score
                    + self.W_SEM_CTX * sem_score
                    + self.W_UNI_CTX * log_prior
                    + domain_bonus
                )
            else:
                score = self.W_FREQ_NOCTX * freq_score + self.W_UNI_NOCTX * log_prior

            char_scores[char] = score

        best = max(char_scores, default=None, key=char_scores.get)
        print(f'Suggestion: {best}')
        return best
