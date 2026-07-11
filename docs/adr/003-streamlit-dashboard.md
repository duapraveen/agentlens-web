# ADR-003: Streamlit for the dashboard

Date: 2026-07-10 · Status: Accepted

## Context
US-3/US-6 need a multi-page internal dashboard (7 pages, 3 personas, drill-downs)
built by a small team on top of the existing SQLAlchemy models. The constitution
sanctions Streamlit and CLAUDE.md's run command already assumes it. Alternatives:
a full web stack (FastAPI + frontend — far more surface for an internal tool) or
plain notebooks (no interactivity model, no nav).

## Decision
**New dependency: `streamlit`.** Structure per the approved UI design
(docs/superpowers/specs/2026-07-10-ui-design.md): shell in `dashboard/app.py` using
`st.navigation(position="hidden")` + `st.page_link` so nav filters by role while
Call Detail stays routable but hidden; layout-only files in `dashboard/pages/`;
all DB reads via plain functions in `dashboard/data.py` (unit-testable, ORM-only).
Headless page tests use `streamlit.testing.v1.AppTest`.

## Consequences
- No auth/user model — role is a sidebar selectbox in session state (per design).
- Streamlit reruns scripts top-to-bottom; anything expensive must be cached or
  triggered explicitly by a button (UI-triggered LLM spend happens only on click).
- Pins a sizeable dependency tree (tornado, pyarrow, pandas) — dev/demo tool cost,
  not shipped to any production path.
