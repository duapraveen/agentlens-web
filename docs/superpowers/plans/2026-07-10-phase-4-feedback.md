# Phase 4 — Human Feedback & Calibration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** US-4 — reviewers confirm/reject judge findings (AC-4.1), judge↔human agreement is computed per dimension and live (AC-4.2), and a revised judge version can be compared side-by-side against the prior version on the golden set with the >2-point regression gate (AC-4.3, constitution IV.3). Backend only; the review UI arrives in Phase 6.

**Architecture:** A `Review` row is one human verdict on one judge finding (`EvalRecord`) — agree/disagree plus an optional note, at most one per finding (resubmission updates in place). `feedback/queue.py` serves the reviewer queue (failed findings, unreviewed first, P0 → P1 → P2) and records verdicts. `feedback/calibration.py` computes agreement stats live from the tables — no caching, so AC-4.2's "updates as reviews land" is free. `feedback/compare.py` composes the existing `compute_judge_quality` (Phase 2) with agreement stats for two judge versions and applies the regression threshold; `jobs/compare_judge.py` prints the side-by-side and exits non-zero when the gate trips. A `--scope golden` option on `jobs/run_evals.py` lets a candidate judge version be evaluated on the golden set only (~$0.15, user-approved, not needed for this phase's exit gate).

**Decisions:**
- **One review per finding** (unique `eval_record_id`): the reviewer's latest verdict wins; `submit_review` upserts. No reviewer identity column — single-reviewer tool for now (YAGNI; add a column when multi-reviewer is real).
- **Agreement definition:** a review of a failed finding *agrees* when verdict == "agree" (human confirms the judge's flag). Agreement rate = agree / reviews, overall and per dimension, filterable by judge config so per-version agreement feeds T403.
- **Regression gate:** candidate flagged when `baseline.precision − candidate.precision > 0.02` or same for recall (precision/recall are 0–1 fractions; constitution's "2 points" = 0.02). Gate result is data (`regression_flagged`), and the compare job also returns exit code 1 so it can block a merge.
- **No LLM spend in this phase:** all tests use seeded reviews and existing eval records. A real candidate-judge comparison run is a later, separately-approved step.

**Tasks:** T401–T403. Zero spend.

## Global Constraints

Same as prior phases: SQLAlchemy 2.0 ORM only, Postgres-portable types, mypy --strict, no transcript content in logs, TDD per task, Conventional Commits referencing `specs/001-agentlens-core/tasks.md#T<id>`.

---

### Task 1: Review model + reviewer queue (T401)

**Files:** Modify `agentlens/models.py` (add `Review`; `EvalRecord.review` relationship). Create `agentlens/feedback/__init__.py`, `agentlens/feedback/queue.py`. Tests: `tests/test_review_model.py`, `tests/test_queue.py`.

**Interfaces:**
- `Review(id int PK, eval_record_id FK unique, verdict str "agree"|"disagree", note str | None, created_at)`; `EvalRecord.review: Mapped[Review | None]`.
- `review_queue(session) -> list[EvalRecord]` — failed findings (`passed == False`), unreviewed first, severity P0 → P1 → P2 within each group, then `id` for determinism.
- `submit_review(session, eval_record_id: int, verdict: Literal["agree","disagree"], note: str | None = None) -> Review` — insert or update the finding's review; flushes, caller commits.

- [ ] Failing tests: Review roundtrip + unique constraint on `eval_record_id`; queue orders unreviewed-first then by severity; `submit_review` creates then updates in place (count stays 1, verdict changes).
- [ ] Implement; verify (pytest/ruff/mypy); commit `feat: review model and reviewer queue (specs/001-agentlens-core/tasks.md#T401)`.

### Task 2: Agreement stats (T402)

**Files:** Create `agentlens/feedback/calibration.py`. Test: `tests/test_calibration.py`.

**Interfaces:** `AgreementStats(n_reviews: int, n_agree: int, agreement: float, per_dimension: dict[str, float], per_dimension_counts: dict[str, int])` (frozen dataclass; agreement is a 0–1 fraction, 0.0 when no reviews); `compute_agreement(session, judge_model: str | None = None, prompt_version: str | None = None) -> AgreementStats` — live query over `Review` joined to `EvalRecord`, optionally filtered to one judge config.

- [ ] Failing tests: mixed agree/disagree reviews across two dimensions produce correct overall + per-dimension rates and counts; empty → zeros; judge-config filter excludes other versions' reviews.
- [ ] Implement; verify; commit `feat: judge-human agreement stats (specs/001-agentlens-core/tasks.md#T402)`.

### Task 3: Judge version comparison + regression gate (T403)

**Files:** Create `agentlens/feedback/compare.py`, `agentlens/jobs/compare_judge.py`. Modify `agentlens/jobs/run_evals.py` (add `--scope golden`). Tests: `tests/test_compare.py`, `tests/test_compare_judge_job.py`, extend `tests/test_run_evals_job.py`.

**Interfaces:**
- `JudgeComparison(baseline: JudgeQuality, candidate: JudgeQuality, baseline_agreement: AgreementStats, candidate_agreement: AgreementStats, precision_delta: float, recall_delta: float, regression_flagged: bool)` — deltas are candidate − baseline; flagged when either delta < −0.02.
- `compare_judge_versions(session, judge_model: str, baseline_version: str, candidate_version: str) -> JudgeComparison`.
- `jobs/compare_judge.py :: main(argv) -> int` — `--baseline`, `--candidate`, `--model` (default settings judge model); logs side-by-side metrics, writes JobRun summary `{baseline, candidate, precision_delta, recall_delta, regression_flagged}`; returns 1 when flagged else 0.
- `run_evals --scope golden` — evaluate golden calls only (runner idempotency still skips already-evaluated ones).

- [ ] Failing tests: seeded golden calls with eval records under two prompt versions (candidate strictly worse) → correct deltas, `regression_flagged=True`, job exit code 1 and JobRun summary; non-regressing candidate → flag False, exit 0; `--scope golden` selects only golden calls.
- [ ] Implement; verify; commit `feat: judge version comparison with regression gate (specs/001-agentlens-core/tasks.md#T403)`.

## Phase 4 Exit Gate

AC-4.1 (queue + agree/disagree + note per finding) ✓ · AC-4.2 (per-dimension agreement, live) ✓ · AC-4.3 (side-by-side version comparison with >2-point regression flag) ✓ — all verified with seeded reviews in tests; fast suite/ruff/mypy clean; `tasks.md` updated. No spend.
