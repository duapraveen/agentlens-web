# Plan — Spec 001: AgentLens Core

Status: Draft for approval · Derived from: `specs/001-agentlens-core/spec.md` · Constitution: v1.0.0
UI reference: `docs/superpowers/specs/2026-07-10-ui-design.md` (approved)

This is the phased development plan. Each phase ends with working, verifiable software
and an explicit exit gate. Detailed step-by-step implementation plans (with code and
tests) are written **one phase at a time, after this plan is approved**, in
`docs/superpowers/plans/`. Task IDs here are the canonical IDs referenced in commits
(`specs/001-agentlens-core/tasks.md#<id>`).

---

## 1. Phasing Rationale

The system is a pipeline: corpus → evals → clusters → human calibration → fixes →
dashboard. Each stage consumes the previous stage's data, so phases follow data
dependencies. The dashboard comes last as a single phase (its own build order is
defined in the UI design doc) because every page reads data produced by phases 1–5;
building UI earlier would mean building against empty tables.

```
Phase 0        Phase 1         Phase 2      Phase 3       Phase 4        Phase 5     Phase 6
Foundation ──► Corpus+Golden ─► Evals ─────► Clustering ─► Calibration ─► Fix loop ─► Dashboard
(no LLM)       (US-7)           (US-1)       (US-2)        (US-4)         (US-5)      (US-3, US-6)
```

LLM spend is gated: phases that call the API list their estimated cost in the exit
gate, and no real-API run happens without explicit user approval (AGENTS.md rule).

## 2. Decisions (resolves spec §6 open questions)

| # | Question | Decision | Rationale |
|---|---|---|---|
| OQ-1 | Cheap bulk judge + expensive escalation? | Single cheap judge (`claude-haiku-4-5`) for the prototype; escalation-on-borderline documented as production path in Phase 2, not built | Meets the < $0.05/call target; measurable against golden set before adding complexity |
| OQ-2 | KMeans vs HDBSCAN | Decide **in Phase 3** by golden-set behavior; leaning KMeans + silhouette-tuned k | scikit-learn already sanctioned by constitution; HDBSCAN would need a new dependency + ADR |
| OQ-3 | Call-level vs per-turn judging | One call-level judgment per conversation covering all four dimensions | Per-turn is ~5x cost; stage attribution is still requested from the judge at call level and validated against golden labels in Phase 2 |
| OQ-4 | Streamlit multipage vs tabs | Multipage | Already decided in the approved UI design doc |
| — | Corpus generator model | `claude-sonnet-5`, configurable via env | Haiku is ~3x cheaper but weaker at realistic multi-turn clinical dialogue; opus-tier is overkill. ~60 short calls ≈ $0.40–0.80 total |
| — | Corpus size & call length | 50–60 transcripts, each ≈1–2 minutes of spoken conversation (≈6–12 short turns) | User decision 2026-07-10 (scope reduction from the original 150–200); golden set freezes 50 of them, satisfying the ≥50 constitution floor |
| — | Cost accounting prices | Sticker prices (haiku $1/$5, sonnet-5 $3/$15 per MTok) | Sonnet 5 intro pricing expires 2026-08-31; we accept slight over-reporting instead of a date-dependent price table |
| — | Embeddings backend | Decide in Phase 3 (sentence-transformers vs API embeddings), with ADR | Heavy dependency (torch) vs an extra API key — needs its own decision when reached |

## 3. Data Model (locked incrementally)

Tables are introduced by the phase that first writes them, so later phases design
against real code rather than speculation:

| Phase | Tables |
|---|---|
| 0 | `calls`, `ground_truth_labels`, `llm_call_log`, `job_runs` |
| 2 | `eval_records`, `deterministic_check_results` |
| 3 | `clusters`, `cluster_members` |
| 4 | `reviews` |
| 5 | `fix_proposals`, `regression_runs` |

All tables: SQLAlchemy 2.0 ORM, portable column types only (Postgres-ready), no raw SQL.

---

## Phase 0 — Foundation (no LLM calls)

**Goal:** Project skeleton every later phase builds on: tooling, settings, database,
the redaction boundary, and the LLM gateway (tested against mocks only).

| ID | Task | Deliverable |
|---|---|---|
| T001 | Project scaffold | `pyproject.toml` (uv, ruff, mypy --strict, pytest with `llm` marker), `.gitignore`, `.env.example`, git init, ADR-001 (initial stack) |
| T002 | Typed settings | `agentlens/config.py` — pydantic-settings: DB URL, golden dir, jobs log path, generator/judge models, API key |
| T003 | DB engine + core models | `agentlens/db.py`, `agentlens/models.py` — `Call`, `GroundTruthLabel`, `LLMCallLog`, `JobRun` |
| T004 | Redaction boundary | `agentlens/privacy/redact.py` — SSN/MRN/phone/email/date patterns → placeholders |
| T005 | LLM gateway | `agentlens/llm/gateway.py` — the only module importing the anthropic SDK: structured JSON via Pydantic, redacts all outbound text, cost in USD cents to `llm_call_log`, prompt-version tagging, unparseable output / refusal recorded as failure |

**Exit gate:** `uv run pytest -m "not llm"` green; ruff + mypy --strict clean; zero API spend.

## Phase 1 — Synthetic Corpus & Golden Set (US-7)

**Goal:** 50–60 short labeled synthetic calls (≈1–2 minutes each) with ~30% injected
failures; frozen golden set (≥50 calls) checked into `data/golden/`.

| ID | Task | Deliverable |
|---|---|---|
| T101 | Taxonomy | `agentlens/corpus/scenarios.py` — 5 scenarios, 6 failure modes (each mapped to pipeline stage, severity, dimension, injection instruction), enums shared by all later phases |
| T102 | Generation prompt | `agentlens/prompts/corpus_generation.py` — versioned template (v1.0) |
| T103 | Transcript generator | `agentlens/corpus/generator.py` — one gateway call → `Call` + optional `GroundTruthLabel`; Pydantic transcript schema |
| T104 | Corpus job | `agentlens/jobs/generate_corpus.py` — `--count/--failure-rate/--seed`; deterministic seeded assignment (exactly `round(count×rate)` failures); `JobRun` row; structlog to `logs/jobs.log` (IDs only, never transcript text) |
| T105 | Golden freeze job | `agentlens/jobs/freeze_golden.py` — stratified selection across (scenario × failure-mode/clean); marks `is_golden`; exports JSON per call; append-only |
| T106 | Corpus run + golden commit | Execute generation (user-approved spend), freeze golden set, commit `data/golden/` |

**Exit gate:** AC-7.1–7.4 verified; est. spend ~$0.50–1 (generation) + ~$0.02 (smoke tests), user-approved before running.

## Phase 2 — Evals: Judge + Deterministic Checks (US-1)

**Goal:** Every call scored on the 4-dimension rubric; deterministic P0 safety checks
independent of the judge; judge quality measured against golden ground truth.

| ID | Task | Deliverable |
|---|---|---|
| T201 | Eval schema | `EvalRecord` (call × dimension: score 0-100, severity, pass/fail, failure description, reasoning, pipeline stage, model/prompt/rubric versions, input hash) + `DeterministicCheckResult` tables; idempotency via unique constraint |
| T202 | Deterministic safety checks | `agentlens/evals/checks.py` — rule-based red-flag-escalation and PHI-readback detectors; run on every call; a deterministic P0 hit is recorded even when the judge scores clean (constitution I.3) |
| T203 | Judge rubric + prompt | `agentlens/prompts/judge.py` — versioned rubric v1.0; Pydantic output model (all 4 dimensions in one call-level judgment, per OQ-3) |
| T204 | Eval runner | `agentlens/evals/runner.py` — evaluate one call via gateway; merge deterministic results; re-running never duplicates records (AC-1.4) |
| T205 | Eval job | `agentlens/jobs/run_evals.py` — `--scope full|unevaluated`, judge model flag, cost estimate printed before run; `JobRun` row |
| T206 | Judge quality metrics | `agentlens/evals/metrics.py` — precision/recall on P0/P1 detection vs golden labels; per-dimension breakdown; stored as the baseline for the regression gate (constitution IV.3) |

**Exit gate:** AC-1.1–1.4 verified; precision & recall ≥ 0.80 on golden set (spec §2) —
if not met, iterate prompt v1.1+ against golden set only; cost/call < $0.05 confirmed
from `llm_call_log`. Est. spend: ~60 calls × haiku ≈ $0.10–0.25 per full pass.

**Exit result (2026-07-10, judge v1.0 baseline):** precision 0.87 ✓, recall 0.72 ✗,
cost 0.35¢/call ✓. Recall shortfall accepted by user decision (2026-07-10): the 5 misses
are wrong_retrieval (0/3) and hallucinated_availability (2/3 missed) — failures a
transcript-only judge structurally cannot verify without reference data. All
transcript-visible modes recall 1.0; the deterministic missed_escalation gate caught 3/3
P0 escalation failures independently. Deferred follow-up: T207 (phi_readback PHONE false
positives, free fix).

## Phase 3 — Failure Clustering (US-2)

**Goal:** Failure descriptions embedded and clustered into labeled, routable patterns.

| ID | Task | Deliverable |
|---|---|---|
| T301 | Embeddings decision + ADR | ADR-002: sentence-transformers vs API embeddings; implement `agentlens/clustering/embed.py` behind a small interface |
| T302 | Clustering | `agentlens/clustering/cluster.py` + `Cluster`/`ClusterMember` tables; KMeans w/ silhouette-tuned k vs HDBSCAN decided by golden-set behavior (OQ-2); re-cluster job `agentlens/jobs/recluster.py` |
| T303 | Cluster labeling | LLM-generated label, 1–2 sentence description, routing suggestion (`prompt_fix / retrieval_data_fix / ops_process / model_config`) via gateway; dominant severity computed from members |
| T304 | Cluster quality check | Script asserting ≥90% of each injected failure mode lands in one dominant cluster on the golden set (AC-2.3) |

**Exit gate:** AC-2.1–2.3 verified. Est. spend: cluster labeling only (~14 clusters × 1 haiku call ≈ cents); embeddings free if local.

**Exit result (2026-07-10):** TF-IDF failed the purity gate (best 4/6 modes at any k;
silhouette ~0.01–0.03) — escalated per ADR-002 to sentence-transformers
(`all-MiniLM-L6-v2`) with judge dimension+stage prefixed into the embedding text;
HDBSCAN evaluated and rejected (OQ-2 closed: KMeans). Final run: 4 labeled clusters
over 73 failed records, purity 1.00 for 5/6 modes; `hallucinated_availability` 0.67 —
one golden call's judge description discusses network status, not availability
(downstream of the accepted Phase 2 recall gap on that mode, 0.33). Deviation accepted
by user decision (2026-07-10). Actual spend: 2.0¢ total (both labeling runs).

## Phase 4 — Human Feedback & Calibration (US-4)

**Goal:** Review queue backend and judge↔human agreement stats (UI arrives in Phase 6).

| ID | Task | Deliverable |
|---|---|---|
| T401 | Review model + queue | `Review` table (finding, verdict agree/disagree, note); queue query (flagged findings, unreviewed first) in `agentlens/feedback/queue.py` |
| T402 | Agreement stats | `agentlens/feedback/calibration.py` — overall + per-dimension agreement %, review counts; recomputed live as reviews land (AC-4.2) |
| T403 | Judge version comparison | Re-run a revised judge prompt/rubric on the golden set; side-by-side precision/recall/agreement vs prior version; >2-point drop flags the regression gate (AC-4.3, constitution IV.3) |

**Exit gate:** AC-4.1–4.3 verified with seeded reviews in tests; comparison runs golden-set-only (~$0.15/run, user-approved).

**Exit result (2026-07-10):** All three ACs verified with seeded reviews in tests
(100 fast tests passing). Zero spend — no LLM calls in this phase. A real candidate
judge (v1.1) comparison run remains available via
`run_evals --scope golden` + `compare_judge --baseline 1.0 --candidate 1.1`
(~$0.15, needs approval) whenever a judge revision lands.

## Phase 5 — Fix Loop: Propose & Validate (US-5)

**Goal:** Close the loop — proposed fix per cluster, regression re-run, before/after delta.

| ID | Task | Deliverable |
|---|---|---|
| T501 | Fix schema | `FixProposal` (cluster, fix type, rationale, patch content) + `RegressionRun` (before/after per-dimension pass rates) tables |
| T502 | Fix proposal | `agentlens/fixes/propose.py` — gateway call generating fix type, rationale, patch (e.g. agent prompt patch) for a selected cluster |
| T503 | Regression re-run | `agentlens/fixes/regression.py` — regenerate the cluster's affected scenarios with the patched agent prompt (`agent_prompt_version` bump), re-run evals on regenerated calls |
| T504 | Before/after report + P0 guard | Per-dimension delta, regression flags on unrelated dimensions; P0 clusters cannot be auto-closed — human acknowledgment required (AC-5.4, constitution V.4) |

**Exit gate:** AC-5.1–5.4 verified; one full closed-loop demo runnable end to end (spec §2). Est. spend per demo loop: regenerate ~10–20 calls + re-eval ≈ $0.30–0.60.

## Phase 6 — Dashboard (US-3, US-6)

**Goal:** The full Streamlit UI per the approved design doc. Build order comes from
that doc — each step leaves a working app with no dead links.

| ID | Task | Deliverable |
|---|---|---|
| T601 | App shell | `agentlens/dashboard/app.py` — sidebar (title, role selector, nav filtered by role, status block), shared CSS, session-state keys; ADR-003 adds streamlit dependency |
| T602 | Jobs page | Corpus/eval/cluster trigger cards + last-run summaries from `job_runs`; job log tail from `logs/jobs.log` |
| T603 | Conversations page | Filters, summary line, paginated table with dimension-dot indicator and P0 flag; row → Call Detail |
| T604 | Call Detail page | Transcript panel, per-dimension expanders (judge reasoning + deterministic results + provenance footer), ground-truth dev toggle (AC-3.1); links to cluster (AC-3.2) |
| T605 | Clusters page | Filter bar, cluster cards, P0-on-top, View-calls / Propose-Fix actions (P0 disabled with tooltip) |
| T606 | Review Queue page | Agreement stats panel, one-finding-at-a-time card, agree/disagree + note + Submit & Next (AC-4.1 UI) |
| T607 | Overview page | 2×2 grid (quality, severity, judge accuracy, top clusters) + cost panel; all numbers drill down within two clicks (AC-6.1, AC-6.2) |
| T608 | Fix Workbench page | Cluster selector, proposed-fix card, regression results table with delta formatting and P0 guard |

**Exit gate:** AC-3.1/3.2 and AC-6.1/6.2 verified; role model matches the UI design's
page-access matrix; demo walkthrough of the full loop (Jobs → Conversations → Call
Detail → Clusters → Fix Workbench; Reviewer flow via Review Queue).

## Phase 7 — End-to-End Validation & Wrap-up

**Goal:** Prove the spec's success metrics on the real corpus and leave the repo demo-ready.

| ID | Task | Deliverable |
|---|---|---|
| T701 | Success-metrics check | Scripted verification of spec §2: judge P/R ≥ 0.80, ≥90% cluster purity, live agreement stats, closed-loop demo, cost/call < $0.05 displayed |
| T702 | Docs | README (setup, demo script, architecture overview); `.env.example` and ADRs current |

**Exit gate:** All spec §2 success metrics demonstrably met or deviations documented; fast suite, ruff, mypy clean.

---

## 4. Cross-Cutting Rules (apply to every phase)

- TDD; fast tests (`-m "not llm"`) run freely; **`-m llm` and real-API jobs only with explicit user approval** — each phase's exit gate lists estimated spend.
- Conventional Commits referencing task IDs; PR-sized phases (trunk-based, short-lived branches).
- Any prompt/rubric/judge/scoring change after Phase 2 re-runs the golden set; >2-point precision or recall drop blocks merge.
- `data/golden/` append-only from the moment T106 lands.
- New dependencies only with an ADR (streamlit, scikit-learn, embeddings backend are the known upcoming ones).

## 5. Review & Approval

This plan is ready for implementation when: phases/tasks cover all spec ACs (traceability
table in `tasks.md`), open questions are resolved or explicitly deferred with a decision
point, and the user approves. After approval, detailed per-phase implementation plans
(with code and tests) are written in `docs/superpowers/plans/`, one phase at a time.
