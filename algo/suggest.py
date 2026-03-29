"""Main procedure to return the guess of next characters.

Copus: Google Ngram (possibly only 2012 corpus)
"""
import json
import random
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
            pass  # If stopwords file doesn't exist, continue without it

    def suggest(self,
                game,
                alpha: float = 1.0,
                beta: float = 0,
                order: bool = True,
                subject: bool = False
                ):
        """Provide suggest according to current solving strategy.

        TODOs:
            length: when len(title) > 6
            non-character: when title contains number or alphabet
            text body info: use ngrams in text body
            domain info: try to hit the domain first -> max prob

        Args:
            game        : game class.
            alpha       : weight of title prior.
            beta        : weight of body text prior.
            order       : to consider the position of known character
            subject     : to consider the subject of known character.
        """
        # judge length of title
        # To use:
        # game.puzzle.title
        # game.puzzle.paragraphs
        # game.all_chars
        # game.title_chars
        # game.guessed_right

        # get masked title
        title = game.puzzle.title
        mask = [char if char in set(game.guessed_right) else '.' for char in title]
        pattern = ''.join(mask)

        # find ngrams that match the pattern
        freq_ngram = {word: freq
                      for word, freq in self._freq[len(title)].items()
                      if re.match(pattern, word)
                      }

        # Build probability distribution for each position
        char_position_prob = defaultdict(lambda: defaultdict(float))
        total_freq = sum(freq_ngram.values()) if freq_ngram else 1

        # For each position that is not yet guessed
        for pos in range(len(title)):
            if title[pos] not in game.guessed_right:
                # Collect all characters at this position from matching ngrams
                # and accumulate their probabilities
                for word, freq in freq_ngram.items():
                    char = word[pos]
                    char_position_prob[pos][char] += freq / total_freq

        # Find the position and character with the highest probability
        best_char = None
        best_prob = 0

        for pos in char_position_prob:
            for char, prob in char_position_prob[pos].items():
                # Skip if character is in stopwords
                if char in self._stopwords:
                    continue
                if char not in game.guessed_right and char not in game.guessed_wrong:
                    if prob > best_prob:
                        best_prob = prob
                        best_char = char

        # Return the character with highest probability
        # If no character found, return a random character from all possible chars
        if best_char is None:
            remaining_chars = game.title_chars - game.guessed_right - game.guessed_wrong
            if remaining_chars:
                best_char = random.choice(list(remaining_chars))

        print(f'Suggestion: {best_char}')
