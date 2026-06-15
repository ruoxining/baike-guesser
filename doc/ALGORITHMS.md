# Baike Guesser — Algorithm Variants

All algorithms share the same constraint: **no Baike article database is assumed**.
The solver knows only what a fluent Chinese reader would know — the Google Ngram
2012 corpus (1–6 grams, ~modern written Chinese frequency distribution), the
domain/entity tags derived from that corpus, and the live feedback from the game.

---

## Shared Infrastructure

### `algo/base.py` — `BaseSuggest`

Common parent for every algorithm.

| Method | What it does |
|---|---|
| `_build_corpus()` | Loads all 1–6 gram JSON + tag files; results are process-level cached. |
| `_load_stopwords()` | Loads `stopwords.txt`; stopword chars are never suggested. |
| `_get_regex_pattern(pattern)` | Cached compiled regex for mask patterns like `'..国'`. |
| `_chunk_body_by_punctuation(text)` | Splits passage text on CJK punctuation into clean chunks. |
| `_get_body_text(game)` | Concatenates all passage paragraphs + author field. |
| `_get_body_chars(game)` | Set of all guessable chars that appear anywhere in the passage. |
| `_get_title_candidates(title, right, wrong)` | All corpus ngrams of length `len(title)` that match the positional mask and contain no wrong chars. |
| `_get_entity_title_candidates(title, right, wrong)` | Like above, but restricted to entity-tagged ngrams; falls back to unconstrained if none survive. |
| `_count_recognised_ngrams(game, body_text)` | Count body chunks consistent with current guesses that match at least one corpus ngram. |
| `_get_ngram_domain(ngram)` | Domain label from the tag file, or `None`. |
| `_is_entity_ngram(ngram)` | Whether the ngram is tagged as a named entity. |
| `_detect_article_domain(game)` | Vote over 2-gram domain tags of confirmed body chars to infer article domain. |

---

## Algorithm A — `ConstraintProp`  *(baseline)*

**File:** `algo/constraint.py`

**Strategy:** Wordle-style hard constraint propagation.

1. Maintain the set of all corpus ngrams of length `len(title)` consistent with
   every piece of feedback received:
   - Correct guesses → positional mask (char must be at that exact position).
   - Wrong guesses → exclusion (ngram must not contain that char anywhere).
2. Count character frequency at still-unknown positions across all surviving
   candidates (weighted by corpus frequency).
3. Suggest the most frequent such character.

**Fallback:** When `len(title) > 6` or no candidates remain, falls back to the
highest-frequency unguessed unigram.

**Complexity:** O(|corpus[n]|) per call where n = title length.

---

## Algorithm B — `EntropyGuess`

**File:** `algo/entropy.py`

**Strategy:** Information-theoretic search — picks the char that maximises the
*expected reduction in Shannon entropy* over the title candidate set.

For every unguessed candidate character `c`:
```
S_hit  = { (ngram, freq) : c appears at some unknown position }
S_miss = candidates − S_hit
p_hit  = Σfreq(S_hit) / Σfreq(all)

E[H | guess c] = p_hit · H(S_hit) + (1 − p_hit) · H(S_miss)
```
We choose `argmin_c E[H | guess c]`.

**Intuition:** A character that splits the candidate set ~50/50 by frequency is
more informative than one present in 99% of candidates, trading short-term hit
probability for faster long-term convergence.

**Fallback:** Empty candidates → highest-frequency unguessed unigram.

**Complexity:** O(|candidates| × |candidate_chars|) per call.

---

## Algorithm C — `BodyBayes`

**File:** `algo/adaptive.py`

**Strategy:** Two-phase body-aware Bayesian approach.

### Phase 1 — Passage Unlock

Guess a pre-ordered list of high-frequency grammatical / temporal words
(`的 是 在 有 年 …`) that are common in encyclopaedic prose but unlikely in
titles.  This unlocks passage ngrams that would otherwise be unrecognisable.

Phase 1 exits when **either** condition is met:
- ≥ `MIN_BODY_HITS = 3` correct guesses confirmed in body, **or**
- ≥ `MIN_RECOGNISED = 2` body chunks now match a corpus ngram.

### Phase 2 — Adaptive Tri-Prob Scoring

Three signals combined with game-state-driven weights:

| Signal | Weight | Description |
|---|---|---|
| `title_ngram_prob` | `alpha` | Position-sensitive: char frequency at unknown positions across ngram candidates matching the current mask. |
| `body_ngram_prob` | `beta` | Position-free: chars appearing in corpus ngrams consistent with all constraints. |
| `recognised_body_prob` | `gamma` | Position-sensitive from body chunks now "recognised" as corpus ngrams. |

**Weight schedule (before renorm):**
```
alpha = clip(0.70 − 0.40·body_evidence + 0.20·title_coverage,  0.15, 0.80)
gamma = clip(0.05 + 0.08·ngram_density,                         0.05, 0.50)
beta  = max(0.05, 1 − alpha − gamma)
```
Where `body_evidence = |right ∩ body| / |right|`,
`title_coverage = |right ∩ title| / |title|`,
`ngram_density` = count of recognised body chunks.

**Design rationale:** Phase 1 makes the gamma signal useful before Phase 2
begins — without it, body chunks are too sparse to identify.  The Bayesian
weight schedule is identical in both phases; no fixed phase-2 weights.

**Complexity:** O(|corpus|) per call; dominated by the body ngram scan.

---

## Algorithm D — `EmbeddingGuess`

**File:** `algo/embedding.py`

**Strategy:** Distributional semantic similarity, built from the ngram corpus.

**Embedding construction (one-time at init):**
For each character `c`, its vector `v(c)` records co-occurrence counts with
every other character across all 2–5 grams, weighted by corpus frequency.
Vectors are L2-normalised so cosine similarity = dot product.

**Scoring at suggestion time:**

1. **freq_score** — character frequency within remaining title candidates.
2. **context_vector** — L2-normalised (domain-boosted) mean of embeddings for
   chars confirmed in the body.  Domain-boosted: chars whose 2-gram tags match
   the detected article domain get weight × 2, sharpening the topic signal.
3. **sem_score** — cosine similarity of candidate char to `context_vector`.
4. **log_prior** — normalised log unigram frequency.

```
score = 0.50·freq_score + 0.35·sem_score + 0.15·log_prior   (with context)
score = 0.80·freq_score + 0.20·log_prior                     (no context)
```

**Complexity:** O(|chars|²·|ngrams|) at init (slow, ~seconds);
O(|candidate_chars|) per call.

---

## Algorithm E — `EntityDomain`

**File:** `algo/entity.py`

**Strategy:** Entity filtering + domain boosting.

**Motivation:** Baike article titles are almost always named entities (persons,
places, organisations, concepts).  Generic ngrams that happen to match the
positional mask are poor candidates.  Restricting to entity-tagged ngrams
dramatically shrinks the candidate set and raises precision.

**Steps:**
1. Detect the article domain by voting over 2-gram domain tags of confirmed body
   chars (`_detect_article_domain`).
2. Filter title candidates to entity-tagged ngrams (`_get_entity_title_candidates`).
   Falls back to unconstrained candidates if none survive.
3. Apply a domain-match multiplier (`DOMAIN_BOOST = 2.5`) to candidates whose
   ngram domain matches the detected article domain.
4. Rank characters at unknown positions by weighted candidate frequency.
5. Fall back to unigram frequency if no candidates remain.

**Intuition:** Domain detection leverages the tagged corpus to distinguish e.g.
a geography article (山脉, 省份 → 地理) from a history article (朝代, 战役 →
史学), further narrowing candidates before the final frequency ranking.

**Complexity:** Same as A (constraint propagation) plus one domain-vote pass.

---

## Algorithm F — `Combined`

**File:** `algo/combined.py`

**Strategy:** Entity-filtered domain-boosted tri-prob scoring + entropy-guided selection.
Combines the complementary strengths of C, E, and B into one pipeline.

### Phase 1 — Passage Unlock

Identical to C, using the same dynamic thresholds (`_phase1_thresholds`).

### Phase 2 — Entity+Domain Tri-Prob + Entropy Selection

**Step 1 — Entity-filtered, domain-boosted candidates (from E):**
Restrict title candidates to entity-tagged ngrams; apply `DOMAIN_BOOST = 2.5` to
candidates whose domain matches the detected article domain.

**Step 2 — Tri-prob scoring (from C):**
Compute `char_title_prob` from the boosted candidates (position-sensitive).
Compute `char_body_prob` and `char_ngram_prob` identically to C.
Combine with C's adaptive weight schedule (`alpha`/`beta`/`gamma`) → `char_posterior`.

**Step 3 — Entropy selection (from B):**
Reweight each entity candidate by the sum of posterior scores for its unknown-position
chars — candidates consistent with likely chars get upweighted.  Then pick the char
that minimises expected Shannon entropy over this posterior-weighted distribution:

```
posterior_candidates[word] = base_freq × (Σ char_posterior[word[pos]] for unknown pos)

argmin_c  p_hit · H(hit_partition) + p_miss · H(miss_partition)
         where partitions are over posterior_candidates
```

**Rationale:** Entity filter and domain boost (E) raise candidate-set *precision*.
Tri-prob (C) adds body-passage evidence.  Entropy (B) then chooses the most
*informative* next guess within this already-filtered, scored space — rather than
simply picking the highest-scoring char, which can be myopic when many candidates
share similar posterior values.

**Complexity:** O(|entity_candidates|²) per call in the worst case (entropy loop);
in practice entity candidates are far fewer than the full ngram set, so this is
faster than running B on unconstrained candidates.

---

## Dynamic Phase 1 Thresholds

`BodyBayes` (C) and `EntityEntropy` (F) both use `_phase1_thresholds(title_len)`
instead of fixed constants, adjusting how long Phase 1 runs based on title length:

| Title length | `min_body_hits` | `min_recognised` | Rationale |
|---|---|---|---|
| ≤ 3 | 1 | 1 | Short named entities rarely contain function words; exit quickly |
| 4–5 | 3 | 2 | Default: balanced body evidence vs. title focus |
| ≥ 6 | 4 | 3 | More unknown positions → more body evidence is worthwhile |

---

## Performance & Trade-off Summary

| ID | Algorithm | Body-context | Entity filter | Domain-aware | Characteristic |
|---|---|---|---|---|---|
| A | `ConstraintProp` | None | No | No | Fastest; clean Wordle-style baseline |
| B | `EntropyGuess` | None | No | No | Best asymptotic convergence; slower per call |
| C | `BodyBayes` | Full (tri-prob) | No | Partial (via body evidence) | Best for long passages; active unlock phase |
| D | `EmbeddingGuess` | Semantic vector | No | Yes (embedding boost) | Useful for rare proper nouns |
| E | `EntityDomain` | Domain vote | Yes | Yes (explicit boost) | Highest precision when entity coverage is good |
| F | `Combined` | Full (tri-prob) | Yes | Yes (explicit boost) | C+E+B combined; highest expected accuracy |

---

## Usage

```python
from algo import (
    ConstraintProp,   # A — baseline
    EntropyGuess,     # B
    BodyBayes,        # C
    EmbeddingGuess,   # D — slow init (~seconds)
    EntityDomain,     # E
    Combined,         # F
)

solver = Combined()
solver.suggest(game)   # prints and returns the suggested character
```

CLI flags:
```
--algo constraint      # A
--algo entropy         # B
--algo body-bayes      # C
--algo embedding       # D
--algo entity          # E
--algo combined        # F
```
