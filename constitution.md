# AgentLens Constitution

Version 1.0.0 · Ratified 2026-07-09 · Applies to all human and AI contributors

AgentLens is an AI conversation quality and observability platform: it evaluates
production (simulated) healthcare voice-agent conversations, detects and clusters
failures, incorporates human reviewer feedback, and validates fixes through
regression evals.

This document is the highest authority in the repository. Specs, plans, tasks,
code, and agent instructions MUST comply with it. Conflicts resolve in this
order: constitution > spec > plan > tasks > code.

---

## Article I — Core Principles

1. **Spec before code.** No feature is implemented without an approved spec
   (`specs/<nnn>-<name>/spec.md`) and plan. Code is regenerable; documents are
   the source of truth.
2. **Measure the measurer.** Any component that judges quality (LLM judge,
   heuristic, classifier) MUST itself have measured accuracy against labeled
   ground truth before its output is trusted or displayed.
3. **Safety is deterministic first.** Safety-critical detections (missed
   escalation of urgent symptoms, PHI exposure) MUST have deterministic
   rule-based checks in addition to any LLM-based judgment. An LLM judge is
   never the sole gate on a P0 safety dimension.
4. **Humans calibrate, machines scale.** Human review is treated as a
   calibration signal (judge↔human agreement), not merely a labeling queue.
   Disagreement above threshold blocks judge-version promotion.
5. **Everything traceable.** Every eval result must be reproducible: pinned
   model version, prompt version, rubric version, input hash. No anonymous
   scores.
6. **Simple until proven otherwise.** Prefer boring technology. New
   infrastructure requires an ADR (`docs/adr/`) explaining why existing tools
   are insufficient.

## Article II — Technology Stack

Aligned with target production environment (Python AI services, GCP,
Kubernetes, Terraform, React frontend, real-time voice pipeline) while staying
prototype-light.

| Layer | Prototype (now) | Production path (design for) |
|---|---|---|
| Language | Python 3.11+ | Same |
| Package/env | `uv` | Same |
| API | FastAPI + Pydantic v2 | Same, behind GCP load balancer |
| Data | SQLite via SQLAlchemy 2.0 (ORM only, no raw SQL) | Cloud SQL Postgres — schema must port with zero code change |
| LLM access | Anthropic API through a single gateway module (`agentlens/llm/gateway.py`) | Same gateway; provider-agnostic interface |
| Embeddings/clustering | sentence-transformers or API embeddings + scikit-learn | Vertex AI / managed |
| UI | Streamlit (internal-tool grade) | React (matches Sage Care frontend) |
| Jobs | CLI-invoked batch (`python -m agentlens.jobs.*`) | K8s CronJobs / queue workers |
| Observability | structlog JSON logs + OpenTelemetry spans (console exporter) | OTel → Cloud Trace / Grafana |
| Infra | Local | GKE + Terraform |

Rules:
- All LLM calls go through the gateway: retries, timeouts, cost accounting,
  and prompt-version tagging live there and nowhere else.
- All LLM outputs are structured (JSON) and validated with Pydantic models.
  Unparseable output is a recorded failure, never silently retried beyond
  the gateway's retry budget.
- No framework lock-in for agent logic: plain Python over heavy agent
  frameworks unless an ADR justifies otherwise.

## Article III — Code Quality

1. Type hints everywhere; `mypy --strict` passes in CI.
2. `ruff` (lint + format) with repo config; zero warnings on main.
3. Public functions and modules carry docstrings stating purpose and units
   (scores are 0-100, costs in USD cents, durations in ms).
4. No function over ~50 lines without justification in review.
5. Configuration via environment variables with a typed `Settings` object
   (pydantic-settings). No secrets in code, logs, or fixtures. `.env` is
   gitignored; `.env.example` is maintained.

## Article IV — Testing & Evaluation

1. **Test-first for logic.** Unit tests written with (or before) implementation;
   pytest; minimum 80% coverage on `agentlens/` core, enforced in CI.
2. **Golden set.** A frozen, labeled set of ≥50 conversations with known
   injected failures lives in `data/golden/`. It is versioned and append-only.
3. **Eval regression gate.** Any change to a prompt, rubric, judge model, or
   scoring code MUST re-run the golden set. Judge precision or recall dropping
   >2 points vs the last accepted run blocks merge.
4. LLM-dependent tests are separated (`-m llm` marker) from fast deterministic
   tests; CI runs fast tests on every push, LLM tests on demand with a cost cap.
5. Every bug fix adds a regression test or golden-set case reproducing it.

## Article V — Data, Privacy & Healthcare Posture

1. **Synthetic data only.** No real patient data ever enters this repository.
   All transcripts are generated; generators must not be seeded with real PHI.
2. **Design for the redaction boundary.** Code paths that send transcript text
   to external APIs pass through `agentlens/privacy/redact.py`, even though
   data is synthetic — the architecture must be HIPAA-plausible.
3. No transcript content in log lines; log IDs and metadata only.
4. Severity taxonomy is fixed: **P0 safety** (missed escalation, PHI exposure,
   harmful guidance) > **P1 accuracy** (wrong facts, hallucinated availability,
   failed task) > **P2 experience** (tone, latency, verbosity). P0 findings are
   never auto-closed by automation; a human must resolve them.

## Article VI — Team Workflow

1. Trunk-based development; short-lived branches; PRs required, no direct
   pushes to `main`.
2. Every PR references the spec/task it implements (`specs/<nnn>/tasks.md#<id>`).
3. Conventional Commits (`feat:`, `fix:`, `eval:`, `docs:`).
4. Architecture decisions recorded as ADRs in `docs/adr/` (context, decision,
   consequences). One page max.
5. CI gates on: ruff, mypy, pytest (fast suite), coverage, and — when eval
   assets changed — the golden-set regression.
6. AI coding agents follow `AGENTS.md` and this constitution; agent-generated
   PRs are reviewed by a human like any other PR.

## Article VII — Amendments

Amend via PR modifying this file with rationale in the description; bump the
semantic version (MAJOR for principle changes, MINOR for new articles/rules,
PATCH for clarifications). Record the change in the log below.

| Version | Date | Change |
|---|---|---|
| 1.0.0 | 2026-07-09 | Initial ratification |
