"""."""
from .constraint import ConstraintProp
from .entropy import EntropyGuess
from .adaptive import BodyBayes
from .embedding import EmbeddingGuess
from .entity import EntityDomain
from .combined import Combined

__all__ = [
    'ConstraintProp',   # A — baseline: Wordle-style constraint propagation
    'EntropyGuess',     # B — information-theoretic: max entropy reduction
    'BodyBayes',        # C — body-aware: function-word unlock + adaptive Bayesian
    'EmbeddingGuess',   # D — semantic: ngram co-occurrence + domain-aware embeddings
    'EntityDomain',     # E — entity-filtered: entity ngrams + domain boost
    'Combined',         # F — entity+domain tri-prob + entropy-guided selection
]
