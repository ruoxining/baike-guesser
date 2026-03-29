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

        # pre-compile regex patterns for performance
        self._pattern_regex_cache = {}

    def _build_corpus(self):
        """Read data from raw corpus."""
        self._freq = defaultdict()
        ngrams = range(1, 7)
        for n in ngrams:
            with open(f'google-ngram-zh-2012/{n}gram.json', 'r', encoding='utf-8') as infile:
                self._freq[n] = json.loads(infile.read())

    def _load_stopwords(self):
        """Load stopwords from file."""
        self._stopwords = set()
        try:
            with open('google-ngram-zh-2012/stopwords.txt', 'r', encoding='utf-8') as infile:
                for line in infile:
                    word = line.strip()
                    if word:
                        self._stopwords.add(word)
        except FileNotFoundError:
            pass  # if stopwords file doesn't exist, continue without it

    def _get_regex_pattern(self, pattern_str: str) -> re.Pattern:
        """Get or create a compiled regex pattern for caching.

        Args:
            pattern_str : the pattern string

        Returns:
            compiled pattern
        """
        if pattern_str not in self._pattern_regex_cache:
            self._pattern_regex_cache[pattern_str] = re.compile('^' + pattern_str + '$')
        return self._pattern_regex_cache[pattern_str]

    def _chunk_body_by_punctuation(self, body_text: str) -> list[str]:
        """Chunk body text into words by punctuation and whitespace.

        Args:
            body_text : the concatenated body text

        Returns:
            chunks    : list of text chunks separated by punctuation
        """
        # Use regex to split by common punctuation marks and whitespace
        # Keep only chunks that contain alphanumeric or CJK characters
        punctuation_pattern = r'[\s，。！？；：''""【】（）、·…—·\n]+'
        chunks = re.split(punctuation_pattern, body_text)
        return [chunk for chunk in chunks if chunk and len(chunk) > 0]

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

        # Pre-compute set combinations for faster lookups
        guessed_right = game.guessed_right
        guessed_wrong = game.guessed_wrong

        # iterate through all ngrams
        for n in range(2, 7):
            if n not in self._freq:
                continue

            for ngram, freq in self._freq[n].items():
                # Convert to set for efficient operations
                ngram_set = set(ngram)

                # contains all guessed_right chars (efficient set operation)
                if not guessed_right.issubset(ngram_set):
                    continue

                # contains any guessed_wrong chars (efficient set operation)
                if guessed_wrong & ngram_set:
                    continue

                # count all chars
                for char in ngram:
                    if char not in guessed_right and char not in guessed_wrong:
                        char_count[char] += freq
                        total_count += freq

        # normalize to probability distribution
        total_count = total_count if total_count > 0 else 1
        char_body_prob = {char: count / total_count
                          for char, count in char_count.items()}

        return char_body_prob

    def _get_recognized_ngram_prob(self, game, body_text: str):
        """Get position-sensitive probability from recognized ngrams in body text.

        Chunks body text by punctuation, then checks if any chunk matches an ngram in the corpus that contains all guessed_right characters and none of the guessed_wrong characters. For each matched chunk, builds a position-sensitive probability distribution.

        Args:
            game            : game class instance
            body_text       : concatenated body text

        Returns:
            char_ngram_prob : dict mapping position to dict of char:probability
        """
        char_ngram_prob = defaultdict(lambda: defaultdict(float))

        # Pre-compute set combinations for faster lookups
        guessed_right = game.guessed_right
        guessed_wrong = game.guessed_wrong

        # Chunk the body text by punctuation
        chunks = self._chunk_body_by_punctuation(body_text)

        for chunk in chunks:
            n = len(chunk)

            # Only consider chunks within the ngram range (1 to 6)
            if n < 1 or n > 6:
                continue

            if n not in self._freq:
                continue

            # Convert chunk to set for efficient operations
            chunk_set = set(chunk)

            # Check if chunk contains all guessed_right (efficient set operation)
            if not guessed_right.issubset(chunk_set):
                continue

            # Check if chunk contains any guessed_wrong (efficient set operation)
            if guessed_wrong & chunk_set:
                continue

            # Build pattern mask to match against corpus
            mask = [char if char in guessed_right else '.' for char in chunk]
            pattern = ''.join(mask)

            # Find matching ngrams in the corpus using pre-compiled regex
            regex_pattern = self._get_regex_pattern(pattern)
            matching_ngrams = {word: freq
                               for word, freq in self._freq[n].items()
                               if regex_pattern.match(word)
                               }

            if not matching_ngrams:
                continue

            # Build position-sensitive probability from matching ngrams
            total_freq = sum(matching_ngrams.values())

            for pos in range(n):
                if chunk[pos] not in guessed_right:
                    for word, freq in matching_ngrams.items():
                        char = word[pos]
                        char_ngram_prob[pos][char] += freq / total_freq

        return char_ngram_prob

    def _combine_probs(self,
                       char_title_prob,
                       char_body_prob,
                       char_ngram_prob,
                       game,
                       alpha: float = 0.7,
                       beta: float = 0.2,
                       gamma: float = 0.1,
                       ):
        """Combine title, body, and recognized ngram probabilities into posterior distribution.

        Args:
            char_title_prob : dict mapping position to dict of char:probability
            char_body_prob  : dict mapping char to probability
            char_ngram_prob : dict mapping position to dict of char:probability (from recognized ngrams)
            alpha           : weight of title prior
            beta            : weight of body text prior
            gamma           : weight of recognized ngram in body text, position-sensitive
            game            : game class instance

        Returns:
            char_posterior  : dict mapping char to posterior probability
        """
        assert abs(alpha + beta + gamma - 1) < 1e-9, f'alpha + beta + gamma must sum to 1, got {alpha + beta + gamma}'

        char_posterior = defaultdict(lambda: [0, 0])  # [sum, count] for averaging

        # Pre-compute commonly used values to avoid repeated calculations
        guessed_combined = game.guessed_right.union(game.guessed_wrong)

        # Pre-compute redistribution weights for when gamma is not used
        total_weight = alpha + beta
        alpha_reweight = alpha / total_weight if total_weight > 0 else 0.5
        beta_reweight = beta / total_weight if total_weight > 0 else 0.5

        # Combine probabilities from title context
        for pos in char_title_prob:
            for char, prob_title in char_title_prob[pos].items():
                # skip if character is in stopwords
                if char in self._stopwords:
                    continue

                if char not in guessed_combined:
                    prob_text = char_body_prob.get(char, 0)
                    prob_ngram = char_ngram_prob.get(pos, {}).get(char, 0)

                    # Only use gamma weight if the position has recognized ngrams
                    if prob_ngram > 0:
                        posterior = alpha * prob_title + beta * prob_text + gamma * prob_ngram
                    else:
                        # Use pre-computed redistribution weights
                        posterior = alpha_reweight * prob_title + beta_reweight * prob_text

                    # accumulate posterior for averaging across positions
                    char_posterior[char][0] += posterior
                    char_posterior[char][1] += 1

        # Also consider characters from recognized ngrams that may not appear in title context
        for pos in char_ngram_prob:
            for char, prob_ngram in char_ngram_prob[pos].items():
                if char in self._stopwords:
                    continue

                if char not in guessed_combined:
                    if char not in char_posterior:
                        # Character appears in recognized ngrams but not title context
                        prob_title = char_title_prob.get(pos, {}).get(char, 0)
                        prob_text = char_body_prob.get(char, 0)
                        posterior = alpha * prob_title + beta * prob_text + gamma * prob_ngram

                        char_posterior[char][0] += posterior
                        char_posterior[char][1] += 1

        # convert to averaged posteriors
        char_posterior = {char: (total / count)
                          for char, (total, count) in char_posterior.items()}

        return char_posterior

    def suggest(self,
                game,
                alpha: float = 0.7,
                beta: float = 0.2,
                gamma: float = 0.1,
                order: bool = True,
                subject: bool = False
                ):
        """Provide suggest according to current solving strategy.

        Args:
            game        : game class.
            alpha       : weight of title prior, position-sensitive.
            beta        : weight of body text prior, position-non-sensitive.
            gamma       : weight of recognized ngram in body text, position-sensitive.
            order       : to consider the position of known character
            subject     : to consider the subject of known character.
        """
        assert abs(alpha + beta + gamma - 1) < 1e-9, f'alpha + beta + gamma must sum to 1, got {alpha + beta + gamma}'

        title = game.puzzle.title

        # Concatenate body text from all paragraphs
        body_text = ''.join(''.join(para) for para in game.puzzle.paragraphs)
        if game.puzzle.author:
            body_text += game.puzzle.author

        # title and body posterior dist
        char_title_prob = self._get_title_prob(title, game.guessed_right)
        char_body_prob = self._get_body_prob(game)
        char_ngram_prob = self._get_recognized_ngram_prob(game, body_text)

        # combine probabilities with weights
        char_posterior = self._combine_probs(
            char_title_prob, char_body_prob, char_ngram_prob, game, alpha, beta, gamma
            )

        # find the character with the highest posterior probability
        best_char = max(char_posterior, default=None, key=char_posterior.get)

        print(f'Suggestion: {best_char}')
