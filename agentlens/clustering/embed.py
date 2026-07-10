"""Embedding backend for failure descriptions (ADR-002: TF-IDF, batch-scoped).

The vectorizer is fit on the batch being clustered, so embeddings are only
comparable within one recluster run. Swap this module's implementation (not
its interface) to escalate to semantic embeddings if golden purity fails.
"""

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer


def embed_texts(texts: list[str]) -> np.ndarray:
    """Dense TF-IDF vectors, one row per input text. Deterministic. Raises on empty input."""
    if not texts:
        raise ValueError("embed_texts requires at least one text")
    vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2))
    matrix = vectorizer.fit_transform(texts)
    dense: np.ndarray = np.asarray(matrix.todense())
    return dense
