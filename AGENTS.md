# AGENTS.md — instructions for AI coding agents

Read `constitution.md` first; it overrides everything including this file.
Current work is defined in `specs/001-agentlens-core/spec.md`.

## Workflow
- Spec → plan → tasks → implement. Do not write feature code without an
  approved spec section and a task ID. Reference the task ID in commits.
- Conventional Commits: `feat:`, `fix:`, `eval:`, `docs:`, `test:`.

## Environment & commands
- Python 3.11+, managed with `uv`.
- Setup: `uv sync`
- Run fast tests: `uv run pytest -m "not llm"`
- Run LLM tests (costs money, ask first): `uv run pytest -m llm`
- Lint/format: `uv run ruff check --fix . && uv run ruff format .`
- Types: `uv run mypy agentlens/`
- Dashboard: `uv run streamlit run agentlens/dashboard/app.py`

## Hard rules
- All LLM calls go through `agentlens/llm/gateway.py`. Never call a provider
  SDK directly from feature code.
- All LLM outputs validated with Pydantic models.
- Never log transcript content; log IDs and metadata only.
- Never modify `data/golden/` except to append new labeled cases.
- Prompt templates live in `agentlens/prompts/` and are versioned; changing
  one requires re-running the golden-set regression.
- Secrets only via env (`.env` gitignored; keep `.env.example` current).
- No new dependencies or frameworks without an ADR in `docs/adr/`.

## Style
- mypy --strict clean, full type hints, docstrings state units
  (scores 0-100, cost in USD cents, durations in ms).
- Prefer plain Python over agent frameworks. Small functions, pure where
  possible; side effects isolated in `jobs/` and `dashboard/`.
