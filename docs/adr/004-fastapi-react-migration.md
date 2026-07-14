# ADR-004: FastAPI + React replaces Streamlit for the dashboard

Date: 2026-07-13 · Status: Accepted · Supersedes: ADR-003

## Context
Constitution Article II already designates the production-path UI as "React
(matches Sage Care frontend)" behind a FastAPI API — Streamlit was explicitly
the *prototype* entry in that table, not the end state. The Streamlit
dashboard (ADR-003) has grown to 7 pages across 3 personas; moving to the
constitution's designated stack now (rather than later) avoids a second
migration and lets the UI adopt a real design system
(docs/superpowers/specs/2026-07-13-streamlit-to-web-migration-design.md).

## Decision
**New dependencies: `fastapi`, `httpx` (required by `fastapi.testclient.TestClient`).**
Structure per docs/superpowers/plans/2026-07-13-streamlit-to-web-migration.md:
`agentlens/api/` exposes one router per existing dashboard page, each a thin
adapter calling the unchanged `agentlens/dashboard/data.py` query layer and
the existing business-logic modules (`feedback/`, `fixes/`, `evals/`) —
no logic is reimplemented in the API layer. The frontend
(`frontend/`, Vite + React + TypeScript, no separate Python dependency) talks
to the API over HTTP; CORS is scoped to the local Vite dev server only.

## Consequences
- `streamlit` is removed once the React frontend is verified working
  end-to-end (final task of the migration plan) — no dual-maintenance period
  beyond that verification window.
- No auth/user model — role selection remains client-side only, matching
  ADR-003's original scope; this is an explicit, revisited non-goal, not an
  oversight.
- The API has no automated coverage for the two LLM-calling Fix Workbench
  mutations (`propose_fix`, `regenerate_for_fix`) — same gap ADR-003's
  Streamlit buttons had; both are verified manually, not in CI, to avoid
  spending LLM budget on every test run.
- `fastapi`/`httpx` are lightweight relative to the dependency tree ADR-003
  already pinned (tornado, pyarrow, pandas via streamlit) — net dependency
  weight decreases once streamlit is removed.
