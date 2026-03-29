# Baike Guesser

![](asset/teaser.png)

## Question Definition

[Guess Baike (猜百科)](https://xiaoce.fun/baike) is a Chinese-language-based puzzle that requires the user to guess the title of a Baike (Chinese Wikipedia) entry.

This solver tries to optimize the guess procedure with the use of Chinese character distribution. To maximize the similarity of the guessing procedures of the algorithm and the human, assumptions are made about the resources achievable by the algorithm.

Assumptions:
1. The algorithm can access the natural Chinese language character distribution (mocked with 2012 Google Ngram), from 1-gram up to 6-gram.
2. The algorithm can know the general domains covered by the Baike, e.g., technology, news, history, etc..
3. The algorithm does not have access to any specific list of keywords under each domain.
4. The algorithm does not know the selection rule of the daily keyword by the Guess Baike website.


##  Solving strategy(ies)

The posterior probability is calculated with the known guesses in the title and the text body.

On each state with the known title context $C_t$, body character set $S_b$, and recognized n-grams in body text $C_b$, for each unguessed character $w$ in the vocabulary:

1. Title probability: $P_s(w|C_t)$: position-sensitive probability from title n-grams matching the current title pattern with known characters fixed.

2. Body probability: $P_i(w|S_b)$: position-insensitive probability from all n-grams (2-6 grams) in the corpus that contain all guessed characters and no wrong guesses.

3. Recognized n-gram probability: $P_r(w|C_b)$: position-sensitive probability from n-grams in body text. The body text is chunked by punctuation marks into phrases (1-6 characters). For each chunk that matches the corpus and contains all guessed characters but no wrong guesses, we extract position-sensitive character probabilities. This probability is only considered when n-grams are actually recognized in the body text.

The three posterior distributions are weighted averaged by:
$$P(w) = \alpha P_s(w|C_t) + \beta P_i(w|S_b) + \gamma P_r(w|C_b)$$

where $\alpha$, $\beta$, and $\gamma$ are configurable weights with $\alpha + \beta + \gamma = 1$. When no recognized n-grams hit for a position, the gamma weight is redistributed to alpha and beta proportionally. Default weights: $\alpha = 0.7$, $\beta = 0.2$, $\gamma = 0.1$.

The suggestion is given by the character with the highest posterior probability.

Improvements:

1. [TODO] Maximize domain possibility: try to hit the domain first -> then max prob.
2. [TODO] Concreteness info: raise weight for concrete words.
3. [TODO] When len(title) > 6, dynamically chunck sub-ngrams.
4. [TODO] To support when title contains numbers or alphabets.


## Interaction

Interaction with Guess Baike website: This program mocks the request to the website, takes the user input, and update to the website.

Before using the suggestion, the ngram frequency data should be downloaded, or build other ngrams through the instruction in this HuggingFace repo.

```bash
git clone https://huggingface.co/datasets/ruoxining/google-ngram-zh-2012
```

Run this command to start interaction.

```bash
python cli.py
```
