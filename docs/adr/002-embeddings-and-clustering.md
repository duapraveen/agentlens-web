# ADR-002: Embeddings backend and clustering algorithm

Date: 2026-07-10 · Status: Accepted

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
