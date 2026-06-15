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


## Solving Strategy

All algorithms share a common base (`algo/base.py`) that loads the Google Ngram corpus and provides shared utilities: corpus access, regex-cached candidate matching, passage chunking by punctuation, and stopword filtering.

On each state with known title context $C_t$, body character set $S_b$, and recognized n-grams in body text $C_b$, the **baseline** (Algo 0) computes:

1. **Title probability** $P_s(w|C_t)$: position-sensitive probability from title n-grams matching the current title pattern with known characters fixed.

2. **Text body probability** $P_i(w|S_b)$: position-insensitive probability from all n-grams (2–6 grams) containing all guessed-right characters and no guessed-wrong characters.

3. **Recognized body n-gram probability** $P_r(w|C_b)$: position-sensitive probability from body text chunks that match the corpus given current constraints.

$$P(w) = \alpha P_s(w|C_t) + \beta P_i(w|S_b) + \gamma P_r(w|C_b)$$

Default weights: $\alpha = 0.5$, $\beta = 0.4$, $\gamma = 0.1$. Phase logic: before any body hit $\beta = 0$; $\gamma$ activates only when recognized body n-grams are found.


## Algorithm Variants

Six algorithms are implemented under `algo/`. All share `BaseSuggest` and expose a unified `suggest(game) -> str | None` interface.

| # | Class | Strategy |
|---|---|---|
| 0 | `Suggest` | Baseline weighted combination of title / body / recognized-ngram probabilities |
| 1 | `EntropyGuess` | Pick the guess that maximises expected Shannon entropy reduction over title candidates |
| 2 | `FunctionWordBridge` | Phase 1: guess function words to unlock passage ngrams; Phase 2: baseline with boosted $\gamma$ |
| 3 | `EmbeddingGuess` | Corpus-derived co-occurrence embeddings; semantic similarity to body-confirmed context |
| 4 | `AdaptiveBayes` | Baseline with game-state-driven $\alpha / \beta / \gamma$ (body evidence, title coverage, ngram density) |
| 5 | `ConstraintPropagation` | Wordle-style hard constraint pruning; frequency ranking over surviving title candidates |

See [ALGORITHMS.md](ALGORITHMS.md) for detailed mechanics, complexity analysis, and trade-off comparisons.


## Setup

Download the ngram frequency data:

```bash
git clone https://huggingface.co/datasets/ruoxining/google-ngram-zh-2012
```


## Usage

**Interactive solver** — mocks requests to the website, takes user input, and updates state:

```bash
python cli.py
```

**Record today's puzzle** — saves to `puzzles/<date>.json` for later benchmarking:

```bash
python record_puzzle.py
python record_puzzle.py --date 20260604      # specific date
```

**Benchmark all algorithms** against saved puzzles:

```bash
python benchmark.py                          # all puzzles, all algorithms
python benchmark.py --algos baseline entropy constraint
python benchmark.py --puzzle puzzles/20260604.json
python benchmark.py --max-guesses 60
```

Results are printed as a summary table and saved to `benchmark_results.json`.
