"""Main procedure to return the guess of next characters.

Copus: Google Ngram (possibly only 2012 corpus)
"""
import json
import re
from collections import defaultdict


class Suggest:
    """Suggest the next characters."""
    def __init__(self):
        """Init function for suggestion class."""
        self._build_corpus()
        self._load_stopwords()

    def _build_corpus(self):
        """Read data from raw corpus."""
        self._freq = defaultdict()
        ngrams = range(1, 7)
        for n in ngrams:
            with open(f'corpus/{n}gram.json', 'r', encoding='utf-8') as infile:
                self._freq[n] = json.loads(infile.read())

    def _load_stopwords(self):
        """Load stopwords from file."""
        self._stopwords = set()
        try:
            with open('corpus/stopwords.txt', 'r', encoding='utf-8') as infile:
                for line in infile:
                    word = line.strip()
                    if word:
                        self._stopwords.add(word)
        except FileNotFoundError:
            pass  # if stopwords file doesn't exist, continue without it

    def _get_title_prob(self, title, guessed_right):
        """Get character probability distribution from title context.

        Args:
            title           : the title string
            guessed_right   : set of already guessed correct characters

        Returns:
            char_title_prob : dict mapping position to dict of char:probability
        """
        mask = [char if char in guessed_right else '.' for char in title]
        pattern = ''.join(mask)

        # find ngrams that match the pattern
        freq_ngram = {word: freq
                      for word, freq in self._freq[len(title)].items()
                      if re.match(pattern, word)
                      }

        # build probability distribution for each position from title
        char_title_prob = defaultdict(lambda: defaultdict(float))
        total_freq_title = sum(freq_ngram.values()) if freq_ngram else 1

        # for each position that is not yet guessed
        for pos in range(len(title)):
            if title[pos] not in guessed_right:
                # collect all characters at this position from matching ngrams
                # and accumulate their probabilities
                for word, freq in freq_ngram.items():
                    char = word[pos]
                    char_title_prob[pos][char] += freq / total_freq_title

        return char_title_prob

    def _get_body_prob(self, game):
        """Get character probability distribution from body text context.

        Uses n-grams to infer character frequencies based on guessed characters.
        Filters n-grams to only include those containing all guessed_right chars
        and none of the guessed_wrong chars.

        Args:
            game            : game class instance

        Returns:
            char_body_prob  : dict mapping char to probability
        """
        char_count = defaultdict(int)
        total_count = 0

        # iterate through all ngrams
        for n in range(2, 7):
            if n not in self._freq:
                continue

            for ngram, freq in self._freq[n].items():
                # contains guessed_right chars
                if not all(char in ngram for char in game.guessed_right):
                    continue

                # contains guessed_wrong chars
                if any(char in ngram for char in game.guessed_wrong):
                    continue

                # count all chars
                for char in ngram:
                    if char not in game.guessed_right and char not in game.guessed_wrong:
                        char_count[char] += freq
                        total_count += freq

        # normalize to probability distribution
        total_count = total_count if total_count > 0 else 1
        char_body_prob = {char: count / total_count
                          for char, count in char_count.items()}

        return char_body_prob

    def _combine_probs(self,
                       char_title_prob,
                       char_body_prob,
                       game,
                       alpha: float = 0.8,
                       beta: float = 0.2
                       ):
        """Combine title and body probabilities into posterior distribution.

        Args:
            char_title_prob : dict mapping position to dict of char:probability
            char_body_prob  : dict mapping char to probability
            alpha           : weight of title prior
            beta            : weight of body text prior
            game            : game class instance

        Returns:
            char_posterior  : dict mapping char to posterior probability
        """
        char_posterior = defaultdict(lambda: [0, 0])  # [sum, count] for averaging

        for pos in char_title_prob:
            for char, prob_title in char_title_prob[pos].items():
                # skip if character is in stopwords
                if char in self._stopwords:
                    continue

                if char not in game.guessed_right.union(game.guessed_wrong):
                    prob_text = char_body_prob.get(char, 0)
                    posterior = alpha * prob_title + beta * prob_text

                    # accumulate posterior for averaging across positions
                    char_posterior[char][0] += posterior
                    char_posterior[char][1] += 1

        # convert to averaged posteriors
        char_posterior = {char: (total / count)
                          for char, (total, count) in char_posterior.items()}

        return char_posterior

    def suggest(self,
                game,
                alpha: float = 0.8,
                beta: float = 0.2,
                order: bool = True,
                subject: bool = False
                ):
        """Provide suggest according to current solving strategy.

        TODOs:
            length: when len(title) > 6
            non-character: when title contains number or alphabet
            text body info: use ngrams in text body (chunk with stopwords?)
            domain info: try to hit the domain first -> then max prob
            concreteness info: raise weight for concrete words.

        Args:
            game        : game class.
            alpha       : weight of title prior, position-sensitive.
            beta        : weight of body text prior, position-non-sensitive (temporarily).
            order       : to consider the position of known character
            subject     : to consider the subject of known character.
        """
        title = game.puzzle.title

        # title and body posterior dist
        char_title_prob = self._get_title_prob(title, game.guessed_right)
        char_body_prob = self._get_body_prob(game)

        # combine probabilities with weights
        char_posterior = self._combine_probs(
            char_title_prob, char_body_prob, game, alpha, beta
            )

        # find the character with the highest posterior probability
        best_char = max(char_posterior, default=None, key=char_posterior.get)

        print(f'Suggestion: {best_char}')
