# Phase 3 — Failure Clustering Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** US-2 — failed eval records are embedded and clustered into labeled patterns; each cluster gets an LLM-generated label, description, and routing suggestion (`prompt_fix / retrieval_data_fix / ops_process / model_config`); ≥90% of each injected failure mode lands in one dominant cluster on the golden set (AC-2.3).

**Architecture:** Clustering operates on the `failure_description` text of failed `EvalRecord`s. A small interface (`clustering/embed.py :: embed_texts`) isolates the embedding backend; `clustering/cluster.py` picks k by silhouette-scanned KMeans (deterministic, `random_state=0`); `clustering/labeling.py` labels each cluster through the gateway (haiku, versioned prompt); `clustering/purity.py` computes per-mode dominant-cluster purity on golden calls. `jobs/recluster.py` wipes and rebuilds `clusters`/`cluster_members` (derived data) and reports purity in its JobRun summary.

**Decisions:**
- **OQ-2 resolved: KMeans + silhouette-tuned k** (k ∈ 2..min(12, n−1)). HDBSCAN would add a dependency + ADR for no demonstrated need at this corpus size; revisit only if purity fails.
- **Embeddings (T301, ADR-002): TF-IDF via scikit-learn first.** The corpus is ~25–40 short, rubric-templated failure descriptions; scikit-learn is needed for KMeans anyway and is constitution-sanctioned; sentence-transformers would pull in torch (~GBs) and Anthropic has no embeddings API (Voyage would mean a second external API + key). Escalation path documented in the ADR: if golden purity < 90% with TF-IDF, switch `embed_texts` to sentence-transformers (interface unchanged) with an ADR amendment.
- **Purity definition:** for each golden ground-truth failure mode, take the member eval record whose dimension matches the mode's expected dimension (fallback: any failed record for that call); purity = share of those members in the mode's most common cluster.
- **Cluster lifecycle:** clusters are derived — every recluster run deletes and rebuilds all rows. Labeling failures degrade gracefully (fallback label `unlabeled_cluster_<n>`, routing `ops_process`) and never fail the run.
- **New dependency:** `scikit-learn` (+ numpy) — ADR-002; mypy override for untyped `sklearn`.

**Tasks:** T301–T304. All mocked/local (zero spend). The real recluster run (labels ~5–12 clusters via haiku, **~$0.01–0.05**) requires user approval.

## Global Constraints

Same as prior phases. Cluster labeling calls go through the gateway with a versioned prompt (`cluster_labeling` v1.0); failure descriptions sent for labeling pass the redaction boundary automatically (gateway).

---

### Task 1: Embeddings backend + ADR-002 (T301)

**Files:** Modify `pyproject.toml` (add `scikit-learn>=1.4`, mypy override for `sklearn.*`). Create `docs/adr/002-embeddings-and-clustering.md`, `agentlens/clustering/__init__.py`, `agentlens/clustering/embed.py`. Test: `tests/test_embed.py`.

**Interfaces:** `embed_texts(texts: list[str]) -> np.ndarray` — dense float array `(n, d)`, deterministic, batch-scoped TF-IDF fit (the vectorizer is fit on the batch being clustered; no persisted vocabulary).

- [ ] Failing tests: shape `(n, d)`; deterministic across calls; texts sharing vocabulary are closer (cosine) than disjoint ones; empty input → `(0, 0)`-safe behavior (raises ValueError).
- [ ] Implement + ADR-002; `uv sync`; verify; commit `feat: TF-IDF embedding backend + ADR-002 (…#T301)`.

### Task 2: Clustering algorithm + tables + recluster job (T302)

**Files:** Modify `agentlens/models.py` (add `Cluster`, `ClusterMember`). Create `agentlens/clustering/cluster.py`, `agentlens/jobs/recluster.py`. Tests: `tests/test_cluster_models.py`, `tests/test_clustering.py`, `tests/test_recluster_job.py`.

**Interfaces:**
- `Cluster(label, description, routing_suggestion, dominant_severity, size, created_at)` + `ClusterMember(cluster_id, eval_record_id unique)`; relationships `Cluster.members`, `ClusterMember.eval_record`.
- `assign_clusters(embeddings: np.ndarray, k_max: int = 12) -> list[int]` — silhouette-scanned KMeans, deterministic; n < 3 → all zeros.
- `jobs/recluster.py :: main(argv) -> int` — gathers failed eval records with descriptions, embeds, assigns, **deletes and rebuilds** cluster tables, labels each cluster via T303 (patched in tests), computes dominant severity (P0 > P1 > P2 among members) and golden purity, JobRun summary `{clusters, failures, purity, cost_cents, duration_ms}`.

- [ ] Failing tests: model roundtrip + unique member; `assign_clusters` groups three obviously distinct synthetic description groups and is deterministic; job persists clusters/members, wipes on re-run (no dupes), summary counts correct (labeling patched).
- [ ] Implement; verify; commit `feat: KMeans clustering, cluster tables, recluster job (…#T302)`.

### Task 3: LLM cluster labeling + routing (T303)

**Files:** Create `agentlens/prompts/cluster_labeling.py`, `agentlens/clustering/labeling.py`. Test: `tests/test_labeling.py`.

**Interfaces:** `ClusterLabel(label: str, description: str, routing: Literal["prompt_fix","retrieval_data_fix","ops_process","model_config"])`; `label_cluster(session, descriptions: list[str], *, model=None, client=None) -> GatewayResult[ClusterLabel]` — samples ≤10 descriptions into the prompt; prompt `cluster_labeling` v1.0.

- [ ] Failing tests: prompt includes sampled descriptions and the four routing options; `label_cluster` returns parsed label via mocked gateway; uses judge model default.
- [ ] Implement; verify; commit `feat: LLM cluster labeling with routing suggestion (…#T303)`.

### Task 4: Cluster purity check (T304)

**Files:** Create `agentlens/clustering/purity.py`. Test: `tests/test_purity.py`. Wire purity into `jobs/recluster.py` summary (done in T302 skeleton; here it becomes real).

**Interfaces:** `compute_mode_purity(session) -> dict[str, float]` — per golden ground-truth failure mode, dominant-cluster share using the dimension-matched member rule above; modes with no clustered members map to 0.0.

- [ ] Failing tests: seeded golden calls/labels/records/members covering a pure mode (1.0), a split mode (0.5), and an unclustered mode (0.0).
- [ ] Implement; verify; commit `feat: golden-set cluster purity check (…#T304)`.

### Exit-gate run — REQUIRES USER APPROVAL (~$0.01–0.05)

- [ ] Approval, then `python -m agentlens.jobs.recluster`; report cluster count, labels/routings, per-mode purity vs the ≥0.90 target, actual cost.
- [ ] If purity < 0.90: escalate embedding backend per ADR-002 (sentence-transformers) and re-run (no LLM cost for re-embedding; labeling again ~pennies) — gated again.
- [ ] Update `tasks.md`; commit.

## Phase 3 Exit Gate

AC-2.1 (failures embedded + clustered; auto label + member count) ✓ · AC-2.2 (routing suggestion per cluster) ✓ · AC-2.3 (≥90% dominant-cluster purity on golden; cluster ↔ member calls linkable via `cluster_members`) ✓ · fast suite/ruff/mypy clean; `tasks.md` updated.
