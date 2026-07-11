# Phase 5 — Fix Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** US-5 — for a selected cluster the system drafts a fix with rationale (AC-5.1); applying it regenerates the affected scenarios with the patched agent and re-runs evals (AC-5.2); a before/after report shows per-dimension pass-rate deltas and flags regressions on unrelated dimensions (AC-5.3); P0 clusters cannot be auto-closed (AC-5.4, constitution V.4).

**Architecture:** `FixProposal` (one drafted fix per cluster, status lifecycle proposed → validated → closed) and `RegressionRun` (one before/after measurement for one fix) are new tables. `fixes/propose.py` drafts the fix through the gateway from the cluster's label + sampled member descriptions. `fixes/regression.py` regenerates each affected call's scenario with a dedicated prompt (`fix_regeneration` v1.0 — corpus prompt untouched) that presents the patch as the agent's updated policy, stamps regenerated calls with `agent_prompt_version=f"fix_{fix.id}"` and `batch_id=f"fixbatch_{fix.id}"`, then evaluates them with the existing runner. `fixes/report.py` computes per-dimension pass rates before (the cluster's affected calls) vs after (the regenerated batch), flags unrelated-dimension regressions, and enforces the P0 close guard. Jobs: `jobs/propose_fix.py --cluster-id N` and `jobs/run_fix_regression.py --fix-id N`.

**Decisions:**
- **Simulation semantics (surfaced tradeoff):** the corpus generator *writes* both sides of the call, so after-fix regeneration cannot honestly test whether the patch would fix a real agent — instructing "inject the failure" and "the agent now behaves correctly" simultaneously is contradictory. After-side generation therefore drops the failure injection and includes the patch as updated agent policy. What the regression report genuinely validates: the loop mechanics end-to-end, and side-effect regressions on unrelated dimensions (a patch that makes the agent verbose or over-disclosing shows up as a communication_quality / safety_compliance drop).
- **New prompt, not a corpus prompt change:** `prompts/fix_regeneration.py` v1.0 reuses the corpus system prompt text with a patched-policy section; `corpus_generation` stays at v1.0 so no golden-set implications.
- **Fix lifecycle:** `status` = "proposed" | "validated" | "closed". `mark_validated` is set by the regression job when it completes. `close_fix(session, fix, actor)` raises on `actor="auto"` when the fix's cluster is P0 (`dominant_severity == "P0"`) — automation can never close a P0 (constitution V.4); any fix may be closed by `actor="human"`.
- **Before/after definition:** before = pass rate per dimension over eval records of the cluster's distinct affected calls (current judge config); after = same over the regenerated batch. `target_dimension` = most common dimension among the cluster's member records; `regressed_dimensions` = dimensions ≠ target whose after-rate < before-rate.
- **Zero spend in tests:** gateway and generation mocked throughout. The real closed-loop demo (regenerate ~5–15 calls + evals, **~$0.30–0.60**) is the exit gate and needs user approval.

**Tasks:** T501–T504.

## Global Constraints

Same as prior phases: gateway-only LLM calls, SQLAlchemy 2.0 ORM, mypy --strict, no transcript content in logs, TDD, Conventional Commits referencing `specs/001-agentlens-core/tasks.md#T<id>`.

---

### Task 1: Fix schema (T501)

**Files:** Modify `agentlens/models.py` (add `FixProposal`, `RegressionRun`; `Cluster.fix_proposals` relationship). Test: `tests/test_fix_models.py`.

**Interfaces:**
- `FixProposal(id int PK, cluster_id FK, fix_type str, rationale Text, patch Text, status str default "proposed", created_at)`; `cluster: Mapped[Cluster]`, `Cluster.fix_proposals: Mapped[list[FixProposal]]`.
- `RegressionRun(id int PK, fix_proposal_id FK, batch_id str, n_before int, n_after int, before_pass_rates JSON dict[str,float], after_pass_rates JSON, target_dimension str, regressed_dimensions JSON list[str], created_at)`; `fix_proposal: Mapped[FixProposal]`.

- [ ] Failing tests: roundtrip both models with relationships; default status "proposed".
- [ ] Implement; verify; commit `feat: fix proposal and regression run tables (specs/001-agentlens-core/tasks.md#T501)`.

### Task 2: Fix proposal (T502)

**Files:** Create `agentlens/prompts/fix_proposal.py`, `agentlens/fixes/__init__.py`, `agentlens/fixes/propose.py`, `agentlens/jobs/propose_fix.py`. Tests: `tests/test_propose.py`, `tests/test_propose_fix_job.py`.

**Interfaces:**
- `ProposedFix(fix_type: Literal["prompt_fix","retrieval_data_fix","ops_process","model_config"], rationale: str, patch: str)` (Pydantic).
- `propose_fix(session, cluster: Cluster, *, model=None, client=None) -> GatewayResult[ProposedFix]` — prompt `fix_proposal` v1.0 from cluster label/description/routing + ≤10 member failure descriptions; judge model default.
- `jobs/propose_fix.py :: main(argv) -> int` — `--cluster-id`; persists a `FixProposal` on success, JobRun summary `{cluster_id, fix_id, fix_type, cost_cents, duration_ms}`; exit 1 if the gateway call failed.

- [ ] Failing tests: prompt includes label, sampled descriptions, four fix types; `propose_fix` returns parsed fix via mocked client; job persists FixProposal and exit codes.
- [ ] Implement; verify; commit `feat: LLM fix proposal for clusters (specs/001-agentlens-core/tasks.md#T502)`.

### Task 3: Regression re-run (T503)

**Files:** Create `agentlens/prompts/fix_regeneration.py`, `agentlens/fixes/regression.py`. Test: `tests/test_regression.py`.

**Interfaces:**
- `affected_calls(session, cluster) -> list[Call]` — distinct calls behind the cluster's member eval records, ordered by id.
- `regenerate_for_fix(session, fix: FixProposal, *, model=None, client=None) -> list[Call]` — one regenerated call per affected call (same scenario, no failure injection, patch as updated policy via prompt `fix_regeneration` v1.0); regenerated calls get `agent_prompt_version=f"fix_{fix.id}"`, `batch_id=f"fixbatch_{fix.id}"`, no ground-truth label; gateway failures skip that call (recorded by gateway).
- Evaluation of regenerated calls reuses `evaluate_call` (wired in the T504 job).

- [ ] Failing tests: regeneration prompt contains patch text and scenario, not the injection framing; `regenerate_for_fix` creates one call per affected call with correct batch/version stamps (mocked client); gateway failure yields fewer calls without raising.
- [ ] Implement; verify; commit `feat: fix regression regeneration (specs/001-agentlens-core/tasks.md#T503)`.

### Task 4: Before/after report + P0 guard + job (T504)

**Files:** Create `agentlens/fixes/report.py`, `agentlens/jobs/run_fix_regression.py`. Tests: `tests/test_fix_report.py`, `tests/test_fix_regression_job.py`.

**Interfaces:**
- `pass_rates(calls: list[Call], judge_model: str, prompt_version: str) -> dict[str, float]` — per-dimension pass fraction over the calls' eval records for one judge config.
- `build_regression_run(session, fix, regenerated: list[Call]) -> RegressionRun` — before/after rates, `target_dimension` (most common member dimension), `regressed_dimensions` (non-target, after < before); persists and returns; sets `fix.status = "validated"`.
- `close_fix(session, fix, actor: Literal["human","auto"]) -> None` — sets status "closed"; raises `PermissionError` when `actor="auto"` and the fix's cluster `dominant_severity == "P0"` (constitution V.4).
- `jobs/run_fix_regression.py :: main(argv) -> int` — `--fix-id`; logs cost estimate, regenerates (T503), evaluates each regenerated call, builds the RegressionRun, JobRun summary `{fix_id, regenerated, evaluated, target_dimension, regressed_dimensions, cost_cents, duration_ms}`.

- [ ] Failing tests: pass-rate math per dimension; report picks target dimension and flags only non-target regressions; `close_fix` P0 auto-close raises / human close succeeds / non-P0 auto-close succeeds; job wires regenerate→evaluate→report with mocks and records JobRun.
- [ ] Implement; verify; commit `feat: before/after regression report with P0 close guard (specs/001-agentlens-core/tasks.md#T504)`.

### Exit-gate run — REQUIRES USER APPROVAL (~$0.30–0.60)

- [ ] Approval, then one closed-loop demo: `propose_fix --cluster-id <P1 cluster>` → `run_fix_regression --fix-id <id>`; report proposal, per-dimension deltas, regressions, actual cost.
- [ ] Update `tasks.md` + plan exit result; commit.

## Phase 5 Exit Gate

AC-5.1 (fix + rationale per cluster) ✓ · AC-5.2 (regenerate + re-eval) ✓ · AC-5.3 (per-dimension delta + unrelated-dimension regression flags) ✓ · AC-5.4 (P0 close guard) ✓ · fast suite/ruff/mypy clean; one closed-loop demo run end to end; `tasks.md` updated.
