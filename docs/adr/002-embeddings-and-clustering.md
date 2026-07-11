# ADR-002: Embeddings backend and clustering algorithm

Date: 2026-07-10 · Status: Accepted · Amended 2026-07-10: escalation exercised (see below)

## Context
Phase 3 clusters failed-eval `failure_description` texts (spec US-2). The corpus is
small (~25-40 short, rubric-templated sentences). Constitution II sanctions
"sentence-transformers or API embeddings + scikit-learn"; spec OQ-2 left
KMeans-vs-HDBSCAN open. Anthropic offers no embeddings API, so API embeddings would
mean a second provider (e.g. Voyage) and key; sentence-transformers pulls in torch
(gigabytes) for a few dozen strings.

## Decision
1. **Embeddings: TF-IDF (scikit-learn)** behind the interface
   `clustering/embed.py :: embed_texts(texts) -> np.ndarray`, fit per batch.
   scikit-learn is required for clustering anyway; no extra dependency.
2. **Clustering: KMeans with silhouette-tuned k** (k ∈ 2..min(12, n-1),
   `random_state=0`) — resolves OQ-2. HDBSCAN rejected for now: extra dependency,
   no demonstrated need at this corpus size.
3. **New dependency: `scikit-learn`** (brings numpy/scipy). mypy override for the
   untyped `sklearn` package.

## Escalation path
The golden-set purity gate (AC-2.3, ≥90% dominant-cluster share per injected mode)
is the empirical test. If TF-IDF fails it, swap `embed_texts` to sentence-transformers
(interface unchanged) and amend this ADR; if cluster-count behavior becomes the
problem, evaluate HDBSCAN then.

## Consequences
- Fully offline, deterministic, free embeddings; clustering results reproducible.
- Batch-scoped vocabulary: embeddings are not comparable across recluster runs —
  acceptable because clusters are derived data, rebuilt on every run.

## Amendment (2026-07-10): escalation exercised

TF-IDF failed the purity gate on the real corpus (73 failed records): no k in 2..12
passed more than 4/6 modes, and silhouette scores were ~0.01-0.03 — no real structure.
Escalated per the path above:

1. **Embeddings: sentence-transformers `all-MiniLM-L6-v2`** (local, free, L2-normalized),
   loaded lazily and cached per process. New dependency `sentence-transformers` (torch).
   Unit tests mock the model; the purity gate validates the real one.
2. **Embedding input is composed text** `"dimension: <d>. stage: <s>. <description>"` —
   description-only embeddings cluster by surface topic (e.g. a dead_end_loop call about
   insurance coverage lands with coverage errors); prefixing the judge's dimension and
   pipeline-stage attribution groups by failure mechanism. Offline scan: desc-only 1/6
   modes ≥0.90 at silhouette-chosen k, composed 5/6 (five at 1.00).
3. **HDBSCAN evaluated and rejected empirically** (OQ-2 stays KMeans): at every
   min_cluster_size 2-5 it marked 16-55/73 records as noise and purity dropped below
   the KMeans result.

Residual known gap: `hallucinated_availability` purity 0.67 — one golden call's judge
description discusses network status, not availability, a direct consequence of the
accepted Phase 2 judge recall gap on that mode (0.33). Better embeddings cannot recover
signal the judge never wrote down.
