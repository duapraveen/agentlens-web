# Phase 2 — Evals Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** US-1 — every call scored on the 4-dimension rubric with one call-level judge call (OQ-3); deterministic P0 safety checks run on every call independent of the judge (constitution I.3); eval runs are idempotent and provenance-stamped (AC-1.3/1.4); judge precision/recall measured against golden ground truth (spec §2 target ≥ 0.80) and stored as the regression-gate baseline.

**Architecture:** Two new tables — `eval_records` (one row per call × dimension, unique on `(call_id, dimension, judge_model, prompt_version)` for idempotency) and `deterministic_check_results` (one row per call × check, unique on `(call_id, check_name)`). Rule-based checks (`evals/checks.py`) are pure functions over the transcript; the runner (`evals/runner.py`) persists check results first, then makes one gateway call with a Pydantic `JudgeOutput` (all four dimensions), then writes four `EvalRecord`s stamped with judge model, prompt version, rubric version, and a sha256 transcript hash. Metrics (`evals/metrics.py`) compute call-level P/R against golden labels — judge-only as the primary "judge quality" number, plus a combined (judge OR deterministic) variant since the P0 gate is deterministic-first. Baselines persist as `JobRun` rows (`job_name="judge_metrics"`), no new table.

**Decisions:**
- **Pass/fail** is derived from the judge's per-dimension `severity`: `passed = severity == "none"`. Scores are 0-100 color; severity is the signal.
- **Deterministic checks** (prototype heuristics, architecture-first): `missed_escalation` = red-flag pattern in a patient turn AND no escalation language in any agent turn; `phi_readback` = identifier pattern (reusing `privacy.redact` patterns via a new public `phi_matches()`) or records-readback phrase in an **agent** turn. A deterministic hit stands even when the judge scores clean — merged downstream, never overwritten.
- **Judge failure handling:** if the gateway call fails, deterministic results still persist; the call stays unevaluated and a re-run retries it (checks skip via their unique constraint).
- **Metrics inclusion rule:** golden calls without eval records are excluded from P/R and reported as `n_missing`.

**Tasks:** T201–T206 from `specs/001-agentlens-core/tasks.md`. All mocked (zero spend). The real eval run + baseline (exit gate) requires **user approval (~$0.15–0.30: ~60 haiku calls)**.

## Global Constraints

Same as Phases 0–1. Additional: any later change to the judge prompt/rubric bumps `PROMPT_VERSION`/`RUBRIC_VERSION` and re-runs the golden set; >2-point P/R drop vs the stored baseline blocks merge (constitution IV.3).

---

### Task 1: Eval schema (T201)

**Files:** Modify `agentlens/models.py` (add `EvalRecord`, `DeterministicCheckResult`, relationships on `Call`). Test: `tests/test_eval_models.py`.

**Interfaces:** `EvalRecord(call_id, dimension, score, severity, passed, failure_description|None, judge_reasoning, pipeline_stage|None, judge_model, prompt_version, rubric_version, input_hash, created_at)` unique on `(call_id, dimension, judge_model, prompt_version)`; `DeterministicCheckResult(call_id, check_name, triggered, detail|None, created_at)` unique on `(call_id, check_name)`; `Call.eval_records` / `Call.check_results` list relationships.

- [ ] Failing tests: roundtrip both tables; uniqueness raises `IntegrityError`; relationships populate.
- [ ] Implement; verify fast suite + ruff + mypy; commit `feat: eval schema (…#T201)`.

### Task 2: Deterministic safety checks (T202)

**Files:** Create `agentlens/evals/__init__.py`, `agentlens/evals/checks.py`; modify `agentlens/privacy/redact.py` (add public `phi_matches(text) -> list[str]`). Tests: `tests/test_checks.py`, extend `tests/test_redact.py`.

**Interfaces:** `CheckOutcome(check_name, triggered, detail|None)`; `run_checks(transcript) -> list[CheckOutcome]` (pure) running `missed_escalation` and `phi_readback`.

- [ ] Failing tests: escalation triggered on red flag + no escalation; not triggered when agent escalates or no red flag; phi triggered on identifier pattern or readback phrase in agent turn only; clean transcript → both untriggered; `phi_matches` returns matched types.
- [ ] Implement; verify; commit `feat: deterministic safety checks (…#T202)`.

### Task 3: Judge rubric + prompt v1.0 (T203)

**Files:** Create `agentlens/prompts/judge.py`. Test: `tests/test_judge_prompt.py`.

**Interfaces:** `PROMPT_NAME="judge"`, `PROMPT_VERSION="1.0"`, `RUBRIC_VERSION="1.0"`, `SYSTEM_PROMPT` (4-dimension rubric, severity taxonomy P0>P1>P2>none, stage attribution, score guidance), `build_user_prompt(transcript) -> str` ("Agent:/Patient:" lines).

- [ ] Failing tests: system prompt names all four dimensions, severities, stages; user prompt renders speaker-labeled lines.
- [ ] Implement; verify; commit `feat: judge rubric and prompt v1.0 (…#T203)`.

### Task 4: Eval runner (T204)

**Files:** Create `agentlens/evals/runner.py`. Test: `tests/test_runner.py`.

**Interfaces:** `DimensionJudgment(score 0-100, severity Literal["P0","P1","P2","none"], failure_description, reasoning, pipeline_stage Literal[stages,"none"])`; `JudgeOutput(task_completion, factual_accuracy, safety_compliance, communication_quality)` with `.for_dimension(Dimension)`; `transcript_hash(transcript) -> str` (sha256[:16], sort_keys); `evaluate_call(session, call, *, model=None, client=None) -> Literal["created","skipped","failed"]`.

- [ ] Failing tests (mocked gateway): creates 4 records with provenance + hash + derived `passed`; persists check results; second run → `"skipped"`, no dupes; gateway failure → `"failed"`, checks persisted, no eval records; retry after failure → `"created"`.
- [ ] Implement; verify; commit `feat: idempotent eval runner (…#T204)`.

### Task 5: Eval job (T205)

**Files:** Create `agentlens/jobs/run_evals.py`. Test: `tests/test_run_evals_job.py`.

**Interfaces:** `main(argv) -> int` with `--scope full|unevaluated` (default `unevaluated`), `--model` (default settings.judge_model). Prints a cost estimate (calls × ~1200 in / ~500 out tokens via `cost_cents`) before running; `JobRun` summary `{scope, model, evaluated, skipped, failed, cost_cents, duration_ms}` where `cost_cents` is the actual sum of `purpose="judge"` log rows created during the run.

- [ ] Failing tests: scope filtering (pre-evaluated call excluded from `unevaluated`); JobRun summary counts with patched `evaluate_call`; estimate logged.
- [ ] Implement; verify; commit `feat: eval batch job (…#T205)`.

### Task 6: Judge quality metrics (T206)

**Files:** Create `agentlens/evals/metrics.py`, `agentlens/jobs/judge_metrics.py`. Test: `tests/test_metrics.py`.

**Interfaces:** `JudgeQuality` dataclass (`n_golden, n_missing, tp, fp, fn, tn, precision, recall, p0_precision, p0_recall, combined_precision, combined_recall, per_mode_recall: dict[str, float]`); `compute_judge_quality(session, judge_model, prompt_version) -> JudgeQuality` — call-level binary: predicted positive = any judge dimension severity in {P0,P1}; actual positive = ground-truth label exists; P0 subset analogous; combined adds deterministic triggers. `jobs/judge_metrics.py` `main(argv) -> int` prints the dataclass as JSON and stores it as a `JobRun(job_name="judge_metrics")` summary (the regression baseline).

- [ ] Failing tests: synthetic golden calls covering TP/FP/FN/TN → exact P/R; P0 subset; per-mode recall; missing-eval exclusion (`n_missing`); zero-division → 0.0; job stores baseline.
- [ ] Implement; verify; commit `feat: judge quality metrics vs golden (…#T206)`.

### Exit-gate run — REQUIRES USER APPROVAL (~$0.15–0.30)

- [ ] Approval, then: `python -m agentlens.jobs.run_evals --scope unevaluated` (60 calls, haiku) → verify 240 eval records + check results; then `python -m agentlens.jobs.judge_metrics` → report precision/recall vs the ≥0.80 target and actual cost/call vs the <$0.05 target.
- [ ] If P/R < 0.80: iterate judge prompt v1.1 against the golden set only (each iteration re-gated on spend), never touching golden labels.
- [ ] Update `tasks.md` statuses; commit.

## Phase 2 Exit Gate

AC-1.1 (per-call per-dimension records with score/severity/description/reasoning/stage) ✓ · AC-1.2 (deterministic checks independent of judge; P0 hit recorded even when judge clean) ✓ · AC-1.3 (model/prompt/rubric versions + input hash on every record) ✓ · AC-1.4 (idempotent re-runs) ✓ · Judge P/R ≥ 0.80 on golden measured and stored as baseline · cost/call < $0.05 confirmed from `llm_call_log`.
