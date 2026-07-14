# Streamlit → FastAPI + React Migration Design

Date: 2026-07-13
Status: Proposed
Spec: 001-agentlens-core
Supersedes UI framework in: [2026-07-10-ui-design.md](2026-07-10-ui-design.md) (that doc's page-by-page *behavior* spec still applies — this doc covers the new *implementation* and *visual design*)

---

## Overview

Replace the Streamlit dashboard (`agentlens/dashboard/app.py` + `pages/*.py`) with a FastAPI JSON backend and a React (Vite + TypeScript) frontend, while preserving all existing business logic untouched. The 7 pages, their filters, navigation flows, and role model from the 2026-07-10 UI design doc carry over unchanged in behavior — only the rendering technology and visual design change.

**What does not change:** `agentlens/dashboard/data.py` (pure ORM query layer), `agentlens/feedback/`, `agentlens/fixes/`, `agentlens/evals/`, `agentlens/jobs/`, `agentlens/llm/gateway.py`, all DB models. These are called directly from new FastAPI route handlers exactly as they were called from Streamlit page scripts.

**What is removed after verification:** `agentlens/dashboard/app.py`, `agentlens/dashboard/ui.py`, `agentlens/dashboard/pages/*.py`, the `streamlit` dependency in `pyproject.toml`.

---

## Architecture

```
agentlens/
  api/                          # NEW
    main.py                     # FastAPI app factory, CORS, router mounts
    deps.py                     # get_db() session dependency (wraps agentlens.db.open_session)
    schemas.py                  # Pydantic response models wrapping dashboard/data.py dataclasses
    routers/
      overview.py                # GET /api/overview
      conversations.py           # GET /api/conversations, GET /api/conversations/{call_id}
      clusters.py                # GET /api/clusters
      review_queue.py            # GET /api/review-queue, POST /api/review-queue/{finding_id}
      fix_workbench.py           # GET /api/fix-workbench/{cluster_id}, POST .../generate, POST .../apply-regression
      jobs.py                    # GET /api/jobs/status, POST /api/jobs/{corpus|evals|recluster}, GET /api/jobs/log
  dashboard/
    data.py                      # UNCHANGED — imported directly by api/routers/*
    ui.py, app.py, pages/        # REMOVED once frontend/ is verified working end-to-end

frontend/                        # NEW — Vite + React + TypeScript, no heavy UI framework
  src/
    api/client.ts                 # typed fetch wrappers, one function per endpoint
    routes/
      Overview.tsx
      Conversations.tsx
      Clusters.tsx
      ReviewQueue.tsx
      FixWorkbench.tsx
      Jobs.tsx
      CallDetail.tsx
    components/
      AppShell.tsx                 # sidebar + role switcher + nav, mounts <Outlet/>
      Card.tsx
      Tabs.tsx
      Table.tsx                    # sortable, paginated, row-click
      Pagination.tsx
      SeverityBadge.tsx
      DimensionDots.tsx
      Slider.tsx, Toggle.tsx, Select.tsx
      StatTile.tsx
      Modal.tsx
      Skeleton.tsx
    styles/
      tokens.css                   # design tokens: color, radius, spacing, type scale
      global.css
    main.tsx, router.tsx
  package.json, vite.config.ts, tsconfig.json
```

**Data flow:** Each FastAPI route calls the same `dashboard/data.py` function the equivalent Streamlit page called, wraps the returned dataclass(es) in a Pydantic model, returns JSON. The React frontend uses React Query for fetching/caching (replacing `st.rerun()`), and moves cross-page state that Streamlit kept in `st.session_state` (`selected_call_id`, `call_detail_origin`, filter values, `fix_cluster_id`, `clusters_filter_id`) into React Router URL state (query params / path params) instead — e.g. `/conversations?cluster=3&severity=P0`, `/call/{call_id}?from=conversations`. This is a direct replacement of the session-state mechanism, not new scope: it makes filtered views linkable/bookmarkable, which session-state string keys never allowed.

**Mutations** (Generate Fix, Apply & Run Regression, Submit Review, launch a job) are `POST` endpoints that call the same business-logic functions Streamlit's button handlers called (`propose_fix`, `regenerate_for_fix`, `evaluate_call`, `build_regression_run`, `submit_review`, `subprocess.Popen(...)` for job launches), then return the updated resource as JSON for the frontend to render. No business logic is duplicated or reimplemented in the API layer — routers are thin adapters.

**Role model:** unchanged from the 2026-07-10 doc — client-side only, no auth. Role lives in a top-level React context / URL, filtering which nav items render, exactly matching today's `st.session_state["role"]` behavior.

**Error handling:** FastAPI returns standard HTTP status codes (404 missing call/cluster, 400 invalid filter/params, 500 on unexpected failure with no transcript content in the error body, matching the "no transcript content in logs" hard rule). The frontend renders an inline error state per component/card — same granularity as today's `st.error`/`st.warning` calls, just as React state instead of Streamlit reruns.

**Testing:** Existing tests for `data.py`, `feedback/`, `fixes/`, `evals/`, `jobs/` are untouched. Add `tests/api/` with FastAPI `TestClient` smoke tests, one per router, covering the happy path and the 404/400 cases. This is new coverage the Streamlit version never had — it's the minimum needed to trust the new HTTP layer, not extra scope.

**Local run:**
```bash
uv run uvicorn agentlens.api.main:app --reload --port 8000     # backend
cd frontend && npm run dev                                      # frontend, port 5173, proxies /api to :8000
```

---

## Design System

Visual language combines two references: (1) a set of reference dashboard screenshots (agent-builder style UI) for dashboard-appropriate component patterns — underline tabs, bordered data cards, table + pagination, slider-with-value-badge, toggle switches, modal structure, category-colored pill tags; (2) the [sage.care](https://www.sage.care/) marketing site for brand palette and typographic tone, since AgentLens is itself a healthcare AI observability product.

### Color tokens

| Token | Value (approx) | Usage |
|---|---|---|
| `--color-primary` | deep teal-green `#0F7864` | primary actions, active tab underline, links, focus rings |
| `--color-primary-dark` | `#0B5C4C` | primary hover/pressed |
| `--color-accent-gradient` | lime `#8FE388` → teal `#2FBFA0` | app wordmark / masthead only — not used in data-dense areas |
| `--color-panel-tint` | pale mint `#F2F9F6` | section backgrounds (e.g. Guardrail-style callouts, filter bars) |
| `--color-surface` | white `#FFFFFF` | card backgrounds |
| `--color-border` | warm gray `#E4E4E0` | card and table borders |
| `--color-text` | near-black `#1A1D1B` | headings, primary text |
| `--color-text-secondary` | gray `#6B706D` | captions, metadata |
| `--severity-p0` | red `#D64545` | P0 badge |
| `--severity-p1` | amber `#C98A1F` | P1 badge |
| `--severity-p2` | slate `#6B7280` | P2 badge |
| Category pill hues | soft mint / soft amber / soft slate fills, one per tag category | Skills/Domain/Intent-style tags, reused for dimension/routing tags |

### Typography

Apple-style system stack: `-apple-system, "SF Pro Text", "SF Pro Display", "Helvetica Neue", Arial, sans-serif` (resolves to San Francisco on macOS/Safari, the closest legitimate match to apple.com without bundling a licensed font).

- Headings: bold/heavy weight, tight tracking, larger scale (matches Apple's heading contrast).
- Body/UI text: regular weight, 14–15px.
- **Text-dense areas** (transcripts, judge reasoning, reviewer notes, patch/code blocks): 14px, line-height 1.45, slightly reduced letter-spacing — tuned for readability at density rather than the larger marketing-site body size.
- Numeric columns (scores, costs, percentages): `font-variant-numeric: tabular-nums` for column alignment.

### Components

- **Buttons:** rounded-rect, ~8px border-radius (not pill-shaped) — matches the reference dashboard's Action/Cancel/Submit buttons. Primary = solid `--color-primary` fill, white text. Secondary = white background, `--color-primary` border + text.
- **Cards:** white surface, 1px `--color-border`, 12px radius, no default shadow; **hover elevation** (subtle shadow lift) on clickable cards/rows (cluster cards, conversation table rows) to signal interactivity — an addition beyond both references, which are static.
- **Tabs:** horizontal underline style, active = bold text + `--color-primary` underline, inactive = gray text.
- **Tags/badges:** soft-fill pill with a 1px border in a deepened shade of the same hue (contrast/accessibility improvement over flat pastel fills).
- **Severity badges:** solid-colored badge with a text label (`P0`, `P1`, `P2`), not emoji dots — accessible and unambiguous in grayscale/colorblind contexts.
- **Tables:** white rows, light-gray header row, hover highlight, bottom-right pagination (Prev/Next + "Page X of Y" + rows-per-page).
- **Sliders:** `--color-primary` track/thumb, current value shown in a small badge above the thumb (matches reference "Response Length" slider).
- **Toggles:** standard switch, `--color-primary` when on.
- **Modals:** centered white card, 12px radius, X close top-right, Cancel (secondary) + primary action bottom-right, dim overlay.
- **Sidebar nav:** icon + label rows; active item indicated by a thin `--color-primary` left-accent bar, not a full-row background fill (quieter than the reference dashboard's sidebar).
- **Loading states:** skeleton placeholders (shimmering gray blocks matching final content shape) for React-Query fetches, rather than blank space or a bare spinner — every page here is a live DB query, unlike a static marketing site.
- **Spacing/radius scale:** 8pt base spacing scale; 12px default card radius, 8px button radius.
- **Dark mode:** color tokens defined as CSS custom properties from the start so a `data-theme="dark"` override is nearly free to add later, even if only light mode ships in v1.

### Component reuse across pages

| Reference pattern | AgentLens usage |
|---|---|
| Agent card (photo + tags + description) | Cluster card (Clusters page) — label, routing/severity tags, description, action buttons |
| History/Audit Log table + pagination | Conversations table, Fix Workbench regression table |
| Guardrails DOs/DONTs panel | Not directly reused; panel-tint background style reused for filter bars |
| Settings sliders/toggles | Jobs page (call count, failure rate slider, judge model select) |
| Tab strip (Configure/Preview/History/...) | Call Detail's dimension score expanders could adopt tab-like grouping if it grows; v1 keeps accordion/expander per behavior spec |

---

## Non-Goals

- No authentication/authorization system (matches current Streamlit behavior — explicitly out of scope per user decision).
- No SSR, no Next.js, no GraphQL, no state-management library beyond React Query.
- No deployment/hosting changes — this is a local-only migration.
- No changes to the page-by-page behavior defined in [2026-07-10-ui-design.md](2026-07-10-ui-design.md) — filters, navigation flows, and role-based visibility carry over exactly.

---

## Open Questions Resolved During Design

- Role handling: client-side only, same as today (no auth). ✓
- Frontend location: new top-level `frontend/` directory (not nested under `agentlens/dashboard/`). ✓
- Streamlit removal: delete `app.py`/`pages/*.py`/`ui.py` and the `streamlit` dependency once the new UI is verified working end-to-end. ✓
