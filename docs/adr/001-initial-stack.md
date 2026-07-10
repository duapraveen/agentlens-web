# ADR-001: Initial technology stack

Date: 2026-07-10 · Status: Accepted

## Context
Constitution Article II fixes the stack shape (Python 3.11+/uv, SQLAlchemy 2.0 on
SQLite, Anthropic API behind a single gateway, Streamlit UI, CLI batch jobs,
structlog). AGENTS.md requires an ADR for every dependency.

## Decision
Adopt exactly the constitution-sanctioned dependencies, nothing else:
`anthropic` (LLM API — gateway only), `pydantic` + `pydantic-settings`
(validation, typed settings), `sqlalchemy>=2.0` (ORM, Postgres-portable),
`structlog` (JSON job logs). Dev: `pytest`, `ruff`, `mypy`.
Deferred until their phase needs them (new ADRs then): `streamlit`,
`scikit-learn`, embeddings backend, OpenTelemetry.

## Consequences
- Plain Python orchestration; no agent frameworks.
- Retries/timeouts rely on the anthropic SDK's built-in retry budget
  (max_retries=2); no separate retry library.
- JSON columns use the portable `sqlalchemy.JSON` type so the schema ports to
  Cloud SQL Postgres with zero code change.
