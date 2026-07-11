# Phase 7 — Validation & Wrap-up Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Verify the five spec §2 success metrics against the live database with a repeatable job, and bring README/docs current. Zero spend.

**Decisions:**
- **T701** `agentlens/jobs/verify_metrics.py`: computes each metric from existing modules (`compute_judge_quality`, `compute_mode_purity`, `compute_agreement`, fix/regression tables, `cost_totals`-equivalent), prints one line per metric with status `PASS` / `FAIL` / `ACCEPTED` (accepted deviations carry the documented reason: judge recall 0.72 and hallucinated_availability purity 0.67, both user-accepted 2026-07-10 and recorded in plan.md). Exit code 1 only on an *unaccepted* FAIL; JobRun summary records everything. Accepted deviations are explicit data in the script — silent threshold-lowering is forbidden.
- **T702** README.md: what the project is, quickstart (uv, .env, jobs, dashboard), architecture table, results summary, spend log, pointers to spec/plan/ADRs/notes. Verify `.env.example` is current.

### Task 1: verify_metrics job (T701)
Files: `agentlens/jobs/verify_metrics.py`; test `tests/test_verify_metrics_job.py` (seeded DB: all-pass case exits 0; an unaccepted regression — e.g. cost over threshold — exits 1; JobRun summary written).
Commit: `feat: success-metrics verification job (specs/001-agentlens-core/tasks.md#T701)`.

### Task 2: README + docs (T702)
Files: `README.md`, `.env.example` check. Commit: `docs: README and docs wrap-up (specs/001-agentlens-core/tasks.md#T702)`.

## Exit Gate
`verify_metrics` runs green (all PASS/ACCEPTED) against the real DB; README current; tasks.md fully ☑; fast suite/ruff/mypy clean.
