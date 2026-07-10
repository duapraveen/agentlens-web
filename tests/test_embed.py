"""Tests for the TF-IDF embedding backend (ADR-002)."""

import numpy as np
import pytest

from agentlens.clustering.embed import embed_texts

_TEXTS = [
    "Agent offered an appointment slot that was never established as available.",
    "Agent invented availability and presented a fabricated slot as fact.",
    "Agent repeated the same clarifying question and ended without completing the task.",
]


def test_shape_and_dtype() -> None:
    matrix = embed_texts(_TEXTS)
    assert isinstance(matrix, np.ndarray)
    assert matrix.shape[0] == 3
    assert matrix.shape[1] > 0


def test_deterministic() -> None:
    a = embed_texts(_TEXTS)
    b = embed_texts(_TEXTS)
    assert np.array_equal(a, b)


def test_shared_vocabulary_is_closer() -> None:
    matrix = embed_texts(_TEXTS)

    def cosine(u: np.ndarray, v: np.ndarray) -> float:
        return float(np.dot(u, v) / (np.linalg.norm(u) * np.linalg.norm(v)))

    availability_pair = cosine(matrix[0], matrix[1])
    unrelated_pair = cosine(matrix[0], matrix[2])
    assert availability_pair > unrelated_pair


def test_empty_input_raises() -> None:
    with pytest.raises(ValueError):
        embed_texts([])
