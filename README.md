# AgentLens

Conversation quality and observability platform for healthcare voice-agent calls.
Every conversation is evaluated by an LLM judge plus deterministic safety checks,
failures are clustered into labeled patterns, human reviewers calibrate the judge,
and proposed fixes are validated by regression evals before being trusted.
**All data is synthetic — no real patient data ever enters this repo.**

Built as a 2–3 day prototype architected for production continuation.
Spec: `specs/001-agentlens-core/spec.md` · Plan & per-phase results:
`specs/001-agentlens-core/plan.md` · Authority order: `constitution.md` > spec > plan > tasks > code.

## Quickstart

```bash
uv sync                                          # install dependencies
cp .env.example .env                             # then set ANTHROPIC_API_KEY

# seed the system (each step costs real API budget; estimates are logged first)
uv run python -m agentlens.jobs.generate_corpus  # ~60 short calls, 30% injected failures (~$0.65)
uv run python -m agentlens.jobs.freeze_golden    # freeze the labeled golden set (free)
uv run python -m agentlens.jobs.run_evals        # judge + deterministic checks (~$0.25)
uv run python -m agentlens.jobs.judge_metrics    # store the judge quality baseline (free)
uv run python -m agentlens.jobs.recluster        # embed + cluster failures (~1¢ labeling)

uv run streamlit run agentlens/dashboard/app.py  # the UI (all jobs also triggerable here)
uv run python -m agentlens.jobs.verify_metrics   # check spec §2 success metrics (free)
```

Development:

```bash
uv run pytest -m "not llm"                       # fast tests (free, run freely)
uv run pytest -m llm                             # hits the real API — costs money
uv run ruff check --fix . && uv run ruff format .
uv run mypy agentlens/
```

## Architecture

| Module | Purpose |
|---|---|
| `agentlens/corpus/` | Synthetic transcript generation with injected failures + ground-truth labels |
| `agentlens/evals/` | LLM judge (4 dimensions, P0/P1/P2) + deterministic safety checks + quality metrics |
| `agentlens/clustering/` | Sentence-transformer embeddings → silhouette-tuned KMeans → LLM-labeled clusters |
| `agentlens/feedback/` | Review queue, judge↔human agreement, judge-version regression gate |
| `agentlens/fixes/` | Fix proposal per cluster, scenario regeneration, before/after regression report |
| `agentlens/dashboard/` | Streamlit UI: 7 pages, 3 roles (Engineer / Reviewer / Lead) |
| `agentlens/llm/gateway.py` | **Single entry point for all LLM calls** — cost accounting, prompt versioning, failure recording |
| `agentlens/privacy/redact.py` | All outbound transcript text passes through PHI redaction |
| `agentlens/jobs/` | CLI batch entrypoints (all side effects live here) |
| `agentlens/prompts/` | Versioned prompt templates — judge changes trigger the golden regression gate |

Data: `data/golden/` is the frozen labeled golden set (append-only);
`data/agentlens.db` is the working SQLite DB (SQLAlchemy 2.0 ORM, Postgres-portable).
Decisions with tradeoffs live in `docs/adr/` (stack, embeddings escalation, streamlit).

## Prototype results (2026-07-10, verified by `verify_metrics`)

| Spec §2 metric | Result |
|---|---|
| Judge precision ≥ 0.80 on golden set | **0.87** ✓ |
| Judge recall ≥ 0.80 | 0.72 — accepted deviation: a transcript-only judge cannot verify retrieval-dependent failures (plan.md Phase 2) |
| ≥ 90% of injected failures in one dominant cluster | 5/6 modes at 1.00; `hallucinated_availability` 0.67 — accepted, downstream of the recall gap (plan.md Phase 3) |
| Agreement visible, recomputed live | ✓ (Review Queue page) |
| Closed-loop demo | ✓ fix #1 (cardiac escalation prompt patch): safety pass rate 0.0 → 1.0 on regenerated calls, no unrelated regressions |
| Cost per evaluated call < $0.05 | **$0.0035** ✓ |

Total prototype LLM spend: ≈ $0.95.

Known limitations and deferred work: `specs/001-agentlens-core/tasks.md` (T207
phi_readback false positives) and `docs/notes/2026-07-10-counterfactual-regression-options.md`
(making fix regression counterfactual).

## Hard rules

- No provider SDK calls outside `agentlens/llm/gateway.py`.
- P0 safety detections are deterministic-first; the LLM judge is never the sole gate,
  and automation can never close a P0 finding (human resolution required).
- No transcript content in logs — IDs and metadata only.
- Judge prompt/rubric/model changes must re-run the golden set; >2-point precision or
  recall drop vs the stored baseline blocks merge (`compare_judge` exits 1).
- New dependencies require an ADR in `docs/adr/`.
