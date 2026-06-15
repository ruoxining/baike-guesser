"""Base class shared by all suggestion algorithms."""
from __future__ import annotations

import json
import pickle
import re
from abc import abstractmethod
from pathlib import Path

from cli.game import is_guessable_char, normalize_guess_char

_CORPUS_DIR = Path('data/google-ngram-zh')

# Module-level cache: shared across all algorithm instances in the same process.
_freq_cache: dict[int, dict[str, float]] = {}
_tags_cache: dict[int, dict[str, dict]] = {}
_stopwords_cache: set[str] | None = None


def _load_ngram(n: int) -> dict[str, float]:
    """Load n-gram frequency dict, using a pickle cache when available."""
    pkl = _CORPUS_DIR / f'{n}gram.pkl'
    json_path = _CORPUS_DIR / f'{n}gram.json'
    if pkl.exists():
        with pkl.open('rb') as f:
            return pickle.load(f)
    with json_path.open('r', encoding='utf-8') as f:
        data: dict[str, float] = json.load(f)
    with pkl.open('wb') as f:
        pickle.dump(data, f, protocol=5)
    return data


def _load_tags(n: int) -> dict[str, dict]:
    """Load tag dict for n-grams if the file exists, else return empty dict."""
    path = _CORPUS_DIR / f'{n}gram_tags.json'
    if not path.exists():
        return {}
    with path.open('r', encoding='utf-8') as f:
        return json.load(f)


def _load_stopwords() -> set[str]:
    words: set[str] = set()
    path = _CORPUS_DIR / 'stopwords.txt'
    try:
        for line in path.read_text(encoding='utf-8').splitlines():
            word = line.strip()
            if word:
                words.add(word)
    except FileNotFoundError:
        pass
    return words


class BaseSuggest:
    """Corpus loading and shared utility methods for all suggesters."""

    def __init__(self) -> None:
        self._build_corpus()
        self._pattern_regex_cache: dict[str, re.Pattern] = {}

    def _build_corpus(self) -> None:
        for n in range(1, 7):
            if n not in _freq_cache:
                _freq_cache[n] = _load_ngram(n)
            if n not in _tags_cache:
                _tags_cache[n] = _load_tags(n)
        self._freq = _freq_cache
        self._tags = _tags_cache

    def _get_ngram_domain(self, ngram: str) -> str | None:
        n = len(ngram)
        return self._tags.get(n, {}).get(ngram, {}).get('domain')

    def _is_entity_ngram(self, ngram: str) -> bool:
        n = len(ngram)
        return self._tags.get(n, {}).get(ngram, {}).get('is_entity', False)

    def _detect_article_domain(self, game) -> str | None:
        """Guess article domain from confirmed body chars via 2-gram tag lookup."""
        body_chars = self._get_body_chars(game)
        confirmed = game.guessed_right & body_chars
        if not confirmed:
            return None
        domain_votes: dict[str, int] = {}
        for ngram, tag in self._tags.get(2, {}).items():
            domain = tag.get('domain')
            if domain and set(ngram).issubset(confirmed):
                domain_votes[domain] = domain_votes.get(domain, 0) + 1
        return max(domain_votes, key=domain_votes.get) if domain_votes else None

    @property
    def _stopwords(self) -> set[str]:
        global _stopwords_cache
        if _stopwords_cache is None:
            _stopwords_cache = _load_stopwords()
        return _stopwords_cache

    def _get_regex_pattern(self, pattern_str: str) -> re.Pattern:
        if pattern_str not in self._pattern_regex_cache:
            self._pattern_regex_cache[pattern_str] = re.compile('^' + pattern_str + '$')
        return self._pattern_regex_cache[pattern_str]

    def _chunk_body_by_punctuation(self, body_text: str) -> list[str]:
        punctuation_pattern = r'[\s，。！？；：‘’“”【】（）、·…—\n]+'
        chunks = re.split(punctuation_pattern, body_text)
        return [chunk for chunk in chunks if chunk]

    def _get_body_text(self, game) -> str:
        body = ''.join(''.join(para) for para in game.puzzle.paragraphs)
        if game.puzzle.author:
            body += game.puzzle.author
        return body

    def _get_body_chars(self, game) -> set[str]:
        body_text = self._get_body_text(game)
        return {
            normalized for char in body_text
            if is_guessable_char(normalized := normalize_guess_char(char))
        }

    def _get_title_candidates(
        self,
        title: str,
        guessed_right: set[str],
        guessed_wrong: set[str],
    ) -> dict[str, float]:
        """Return ngrams matching positional constraints, excluding wrong chars."""
        n = len(title)
        if n not in self._freq:
            return {}
        mask = ''.join(c if c in guessed_right else '.' for c in title)
        regex = self._get_regex_pattern(mask)
        return {
            word: freq
            for word, freq in self._freq[n].items()
            if regex.match(word) and not (guessed_wrong & set(word))
        }

    def _get_entity_title_candidates(
        self,
        title: str,
        guessed_right: set[str],
        guessed_wrong: set[str],
    ) -> dict[str, float]:
        """Like _get_title_candidates but restricted to entity-tagged ngrams.

        Falls back to all candidates if no entity ngrams survive the filter.
        """
        candidates = self._get_title_candidates(title, guessed_right, guessed_wrong)
        entity_only = {w: f for w, f in candidates.items() if self._is_entity_ngram(w)}
        return entity_only if entity_only else candidates

    def _count_recognised_ngrams(self, game, body_text: str) -> int:
        """Count body chunks consistent with current guesses that match corpus ngrams."""
        count = 0
        guessed_right = game.guessed_right
        guessed_wrong = game.guessed_wrong
        for chunk in self._chunk_body_by_punctuation(body_text):
            n = len(chunk)
            if n < 1 or n > 6 or n not in self._freq:
                continue
            chunk_set = set(chunk)
            if not guessed_right.issubset(chunk_set):
                continue
            if guessed_wrong & chunk_set:
                continue
            mask = ''.join(c if c in guessed_right else '.' for c in chunk)
            if any(self._get_regex_pattern(mask).match(w) for w in self._freq[n]):
                count += 1
        return count

    @abstractmethod
    def suggest(self, game) -> str | None: ...
