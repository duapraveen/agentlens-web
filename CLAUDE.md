# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Authority Order

`constitution.md` overrides everything. `specs/<nnn>/spec.md` overrides plans, tasks, and code. Consult them first on any ambiguity.

## What This Project Is

AgentLens is an AI conversation quality and observability platform for healthcare voice-agent conversations. It evaluates transcripts, clusters failures, calibrates an LLM judge against human reviewers, and validates fixes via regression evals. All data is synthetic — no real patient data ever enters the repo.

## Commands

```bash
uv sync                                         # install/sync dependencies
uv run pytest -m "not llm"                      # fast tests (run freely)
uv run pytest -m llm                            # LLM tests (cost money — ask first)
uv run ruff check --fix . && uv run ruff format .  # lint + format
uv run mypy agentlens/                          # type-check
uv run uvicorn agentlens.api.main:app --reload --port 8000  # backend API
cd frontend && npm run dev                      # frontend dev server (http://localhost:5173)
python -m agentlens.jobs.<name>                 # run a batch job
```

## Architecture

Monorepo Python package `agentlens/` with these modules:

| Module | Purpose |
|---|---|
| `corpus/` | Synthetic transcript generation with injected failures and ground-truth labels |
| `evals/` | LLM judge + deterministic safety checks; produces per-call, per-dimension scores |
| `clustering/` | Embed failure descriptions and cluster into labeled patterns |
| `feedback/` | Human review queue; computes judge↔human agreement and calibration stats |
| `fixes/` | Propose fixes for clusters, regenerate affected scenarios, run before/after regression |
| `dashboard/data.py` | Pure ORM query layer backing the API (no UI framework imports) |
| `api/` | FastAPI backend; one router per page, calling `dashboard/data.py` and the modules above |
| `llm/gateway.py` | **Single entry point for all LLM calls** — retries, cost accounting, prompt-version tagging |
| `privacy/redact.py` | All transcript text bound for external APIs passes through here |
| `jobs/` | CLI-invoked batch entrypoints (side effects live here, not in core modules) |
| `prompts/` | Versioned prompt templates — changes require re-running golden-set regression |

Data layout:
- `data/golden/` — frozen labeled subset (≥50 calls); append-only, never modify existing entries
- `data/` — generated synthetic corpora and eval outputs

## Hard Rules

- **Never call a provider SDK directly** — all LLM calls go through `agentlens/llm/gateway.py`.
- All LLM outputs are structured JSON validated with Pydantic models. Unparseable output is a recorded failure.
- P0 safety detections (missed escalation, PHI exposure) require deterministic rule-based checks in addition to any LLM judge — the LLM is never the sole gate.
- No transcript content in log lines; log IDs and metadata only.
- New dependencies require an ADR in `docs/adr/`.
- Secrets via env only; `.env` is gitignored; keep `.env.example` current.

## Workflow

1. Spec → plan → tasks → implement. No feature code without an approved spec section and task ID.
2. Reference the task ID in every commit (`specs/001/tasks.md#<id>`).
3. Conventional Commits: `feat:`, `fix:`, `eval:`, `docs:`, `test:`.
4. PRs required; no direct pushes to `main`.

## Eval Regression Gate

Any change to a prompt template, rubric, judge model, or scoring code **must** re-run the golden set (`data/golden/`). Judge precision or recall dropping >2 points vs the last accepted run blocks merge.

## Style

- `mypy --strict` clean; full type hints everywhere.
- Docstrings state purpose and units: scores are 0-100, costs in USD cents, durations in ms.
- No function over ~50 lines without justification.
- Prefer plain Python over agent frameworks.
- Database: SQLAlchemy 2.0 ORM only (no raw SQL) — schema must port to Postgres with zero code change.
- Severity taxonomy: **P0 safety** > **P1 accuracy** > **P2 experience**. P0 findings require human resolution; automation cannot close them.
