"""Cluster assignment: KMeans with silhouette-tuned k (ADR-002, resolves OQ-2)."""

import numpy as np
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score


def assign_clusters(embeddings: np.ndarray, k_max: int = 12) -> list[int]:
    """Assign a cluster index to each embedding row.

    Scans k in 2..min(k_max, n-1) and picks the best silhouette score.
    Deterministic (random_state=0). Fewer than 3 rows collapse to one cluster.
    """
    n = embeddings.shape[0]
    if n < 3:
        return [0] * n
    best_labels: list[int] = [0] * n
    best_score = -1.0
    for k in range(2, min(k_max, n - 1) + 1):
        kmeans = KMeans(n_clusters=k, random_state=0, n_init=10)
        labels = kmeans.fit_predict(embeddings)
        if len(set(labels)) < 2:
            continue
        score = float(silhouette_score(embeddings, labels))
        if score > best_score:
            best_score = score
            best_labels = [int(label) for label in labels]
    return best_labels
