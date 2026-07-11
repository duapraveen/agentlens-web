# Phase 6 — Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** US-3 + US-6 — a multi-page Streamlit app per the approved UI design (docs/superpowers/specs/2026-07-10-ui-design.md): role-filtered nav, Jobs / Conversations / Call Detail / Clusters / Review Queue / Overview / Fix Workbench, every number drilling down to calls within two clicks. Build order per the design; each task leaves the app working with no dead links.

**Architecture:** `agentlens/dashboard/app.py` is the shell: role selector, `st.navigation` over `st.Page` objects filtered by the role table, shared CSS, sidebar status block. Pages live in `agentlens/dashboard/pages/` and contain layout only — all queries go through `agentlens/dashboard/data.py` (plain functions, session-scoped, ORM only, unit-tested without Streamlit), and shared rendering helpers (severity badge, four-dot dimension indicator, pass-rate delta arrows) live in `agentlens/dashboard/ui.py`. Job buttons shell out to `python -m agentlens.jobs.*` via subprocess exactly as the CLI does. Streamlit's headless `AppTest` provides per-page smoke tests.

**Decisions:**
- **New dependency `streamlit` → ADR-003** (constitution-sanctioned dashboard surface; CLAUDE.md run command already assumes it).
- **`st.navigation` + `st.Page`** (not the `pages/` autoload convention) because nav must filter by role; `st.switch_page` still works for row-click drill-down.
- **Session state keys** exactly as the design: `role`, `selected_call_id`, `call_detail_origin`, `fix_cluster_id`; pages must tolerate missing keys (direct AppTest loads).
- **Testing split:** `data.py` functions get real unit tests (seeded DB); pages get AppTest smoke tests (page renders, key elements present, filters narrow results). Subprocess job-launching is stubbed in tests.
- **UI-triggered spend** (Run Evals, Generate Fix, regression) executes only on user click in a live session — nothing in this phase spends during build or tests.

**Tasks:** T601–T608, one per design page plus the shell. Zero build spend.

## Global Constraints

Same as prior phases; plus (from the design): no raw SQL, no transcript content in logs, all LLM calls via the gateway, P0 findings require human resolution — Propose Fix disabled on P0 clusters.

---

### Task 1: App shell + ADR-003 (T601)
**Files:** `pyproject.toml` (add streamlit), `docs/adr/003-streamlit-dashboard.md`, `agentlens/dashboard/__init__.py`, `agentlens/dashboard/app.py`, `agentlens/dashboard/data.py` (status block queries), `agentlens/dashboard/ui.py` (CSS, badges, dots). Tests: `tests/test_dashboard_data.py`, `tests/test_app_shell.py` (AppTest: shell renders, role selector changes nav items).
**Produces:** `data.py :: status_summary(session) -> StatusSummary(last_eval_at, n_calls, n_golden)`; `ui.py :: dimension_dots(failed: set[str]) -> str`, `severity_badge(sev) -> str`, `inject_css() -> None`; role→pages table `PAGES_BY_ROLE`.

### Task 2: Jobs page (T602)
**Files:** `agentlens/dashboard/pages/jobs.py`; `data.py :: last_job_run(session, job_name) -> JobRun | None`, `tail_log(path, n=20) -> list[str]`. Tests extend the two test files.
Cards: corpus generation (count default 60 — not the design's stale 200; scope was reduced), eval run (scope radio, model select, client-side estimate), recluster; job-log tail panel. Buttons run `subprocess.Popen([sys.executable, "-m", "agentlens.jobs..."])` (stubbed in tests).

### Task 3: Conversations page (T603)
**Files:** `agentlens/dashboard/pages/conversations.py`; `data.py :: conversation_rows(session, severity=None, dimension=None, cluster_id=None, outcome=None) -> list[ConversationRow]` (per call: id, scenario, failed-dimension set, has_p0, avg score, cost, created_at). Filters, summary line, 25-row pagination, row select → `selected_call_id` + switch to Call Detail.

### Task 4: Call Detail page (T604)
**Files:** `agentlens/dashboard/pages/call_detail.py`; `data.py :: call_detail(session, call_id) -> CallDetail` (call, transcript, per-dimension records, check results, cluster link info, ground truth). Transcript panel, one expander per dimension (score/severity/pass/stage header; reasoning + deterministic results + provenance footer inside), Engineer-only ground-truth toggle, back-link via `call_detail_origin`.

### Task 5: Clusters page (T605)
**Files:** `agentlens/dashboard/pages/clusters.py`; `data.py :: cluster_cards(session, routing=None, severity=None) -> list[ClusterCard]` (label, description, routing, dominant severity, size, id). P0 cards sorted first + red border; `View N calls` → Conversations filtered by cluster; `Propose Fix` → Fix Workbench with `fix_cluster_id` (disabled on P0 with the design's tooltip).

### Task 6: Review Queue page (T606)
**Files:** `agentlens/dashboard/pages/review_queue.py`; reuses `feedback.queue` + `feedback.calibration`. Agreement panel (compute_agreement), one finding at a time from `review_queue()`, transcript expander, Agree/Disagree selection + note + `Submit & Next` (submit_review + rerun), queue-clear state.

### Task 7: Overview page (T607)
**Files:** `agentlens/dashboard/pages/overview.py`; `data.py :: quality_panel(session) -> dict[str, DimensionQuality]` (pass rate + 7-day delta), `severity_counts(session) -> dict[str, int]`, `top_clusters(session, n=5)`, `cost_totals(session) -> CostTotals(total_cents, avg_per_call_cents)`; judge accuracy from stored judge_metrics JobRun baseline + compute_agreement. 2×2 grid + cost line; severity counts link → Conversations, top clusters link → Clusters (two-click drill-down, AC-6.2).

### Task 8: Fix Workbench page (T608)
**Files:** `agentlens/dashboard/pages/fix_workbench.py`; reuses `fixes.propose`, `fixes.regression`, `fixes.report`; `data.py :: latest_fix(session, cluster_id)`, `latest_regression(session, fix_id)`. Non-P0 cluster selector (pre-selected via `fix_cluster_id`), Generate Fix (propose_fix via gateway on click), Apply & Run Regression (regenerate → evaluate → build_regression_run on click), results table with deltas/⚠/>5pp banner, P0 guard disabling the run button.

Each task: failing test → implement → `pytest -m "not llm"` + ruff + mypy → commit `feat: dashboard <page> (specs/001-agentlens-core/tasks.md#T60x)`.

## Phase 6 Exit Gate
All pages render via AppTest with seeded data; role table enforced; AC-3.1/3.2 (call drill-down with per-dimension explanations + provenance), AC-2.3 link path, AC-4.1 (queue UI), AC-6.1/6.2 (overview + two-click drill-down), AC-5.x surfaced in Fix Workbench with the P0 guard; fast suite/ruff/mypy clean; manual `streamlit run` smoke check by user.
