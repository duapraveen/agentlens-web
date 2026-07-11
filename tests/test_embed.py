"""Tests for the sentence-embedding backend (ADR-002, escalated). Model mocked."""

import numpy as np
import pytest

from agentlens.clustering import embed


class _FakeModel:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def encode(self, texts: list[str], *, normalize_embeddings: bool = False) -> np.ndarray:
        self.calls.append({"texts": texts, "normalize_embeddings": normalize_embeddings})
        rows = np.asarray([[float(len(t)), 1.0] for t in texts])
        norms: np.ndarray = np.linalg.norm(rows, axis=1, keepdims=True)
        return rows / norms


def test_one_row_per_text_normalized(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeModel()
    monkeypatch.setattr(embed, "_model", lambda: fake)
    matrix = embed.embed_texts(["short", "a much longer description"])
    assert isinstance(matrix, np.ndarray)
    assert matrix.shape[0] == 2
    assert fake.calls == [
        {"texts": ["short", "a much longer description"], "normalize_embeddings": True}
    ]


def test_empty_input_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(embed, "_model", lambda: _FakeModel())
    with pytest.raises(ValueError):
        embed.embed_texts([])
