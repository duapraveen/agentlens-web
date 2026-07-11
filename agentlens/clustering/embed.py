"""Embedding backend for failure descriptions (ADR-002, escalated to sentence-transformers).

TF-IDF was the initial backend but failed the golden purity gate (AC-2.3);
per the ADR-002 escalation path this module now encodes with a local
sentence-transformers model. The model loads lazily on first use and is
cached for the process lifetime.
"""

from functools import lru_cache
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer

_MODEL_NAME = "all-MiniLM-L6-v2"


@lru_cache(maxsize=1)
def _model() -> "SentenceTransformer":
    from sentence_transformers import SentenceTransformer

    model: SentenceTransformer = SentenceTransformer(_MODEL_NAME)
    return model


def embed_texts(texts: list[str]) -> np.ndarray:
    """L2-normalized sentence embeddings, one row per input text. Raises on empty input."""
    if not texts:
        raise ValueError("embed_texts requires at least one text")
    return np.asarray(_model().encode(texts, normalize_embeddings=True))
