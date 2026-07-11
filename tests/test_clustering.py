"""Tests for the silhouette-scanned KMeans assignment (synthetic vectors; no model)."""

import numpy as np

from agentlens.clustering.cluster import assign_clusters

_CENTERS = [(0.0, 0.0), (10.0, 0.0), (0.0, 10.0)]
_OFFSETS = [(0.0, 0.1), (0.1, 0.0), (-0.1, -0.1)]


def _three_tight_groups() -> np.ndarray:
    return np.asarray([(cx + ox, cy + oy) for cx, cy in _CENTERS for ox, oy in _OFFSETS])


def test_assign_clusters_groups_similar_vectors() -> None:
    labels = assign_clusters(_three_tight_groups())
    first, second, third = labels[0:3], labels[3:6], labels[6:9]
    assert len(set(first)) == 1
    assert len(set(second)) == 1
    assert len(set(third)) == 1
    assert len({first[0], second[0], third[0]}) == 3


def test_assign_clusters_deterministic() -> None:
    embeddings = _three_tight_groups()
    assert assign_clusters(embeddings) == assign_clusters(embeddings)


def test_tiny_input_single_cluster() -> None:
    assert assign_clusters(np.asarray([[1.0, 0.0]])) == [0]
    assert assign_clusters(np.asarray([[1.0, 0.0], [0.0, 1.0]])) == [0, 0]
