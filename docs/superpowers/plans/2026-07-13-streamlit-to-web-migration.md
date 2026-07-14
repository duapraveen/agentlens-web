# Streamlit → FastAPI + React Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Streamlit dashboard with a FastAPI JSON backend and a React (Vite + TypeScript) frontend, preserving all existing business logic untouched.

**Architecture:** `agentlens/api/` exposes one FastAPI router per existing dashboard page, each calling the same `agentlens/dashboard/data.py` functions and business-logic modules (`feedback/`, `fixes/`, `evals/`) the Streamlit pages called — routers are thin JSON adapters, no reimplemented logic. `frontend/` is a Vite + React + TypeScript app (React Router for navigation, React Query for server-state fetching/caching) that replaces `st.session_state` cross-page state with URL params and replaces Streamlit widgets with hand-rolled components styled from a shared design-token CSS file.

**Tech Stack:** FastAPI, Pydantic v2, SQLAlchemy 2.0 (unchanged), pytest + FastAPI TestClient (backend tests); Vite, React 18, TypeScript, react-router-dom, @tanstack/react-query (frontend).

## Global Constraints

- `mypy --strict` clean on all new Python code; full type hints everywhere.
- No raw SQL — all DB access via the existing SQLAlchemy 2.0 ORM functions in `dashboard/data.py` and the business-logic modules.
- No transcript content in log lines or error messages — IDs and metadata only.
- No provider SDK calls outside `agentlens/llm/gateway.py` — routers call `propose_fix`/`regenerate_for_fix`/`evaluate_call`, never the Anthropic SDK directly.
- P0 severity gating (`fixes/report.py`, `dominant_severity == "P0"`) must be enforced server-side in the API, not just hidden in the UI — the Streamlit version only disabled the button client-side; the API must return 4xx if called anyway.
- Scores are 0–100, costs are USD cents, durations are ms (existing convention, unchanged).
- Conventional Commits (`feat:`, `fix:`, `docs:`, `test:`); reference this plan's path (`docs/superpowers/plans/2026-07-13-streamlit-to-web-migration.md`) in commit bodies since this migration predates task IDs in `specs/001/tasks.md`.
- Design tokens (colors, radius, spacing, type stack) must match `docs/superpowers/specs/2026-07-13-streamlit-to-web-migration-design.md` exactly — no ad hoc colors in component code.

---

## File Structure

```
agentlens/api/
  __init__.py
  main.py            # FastAPI app factory + CORS + router mounts + /api/health
  deps.py            # get_db() session dependency
  schemas.py          # Pydantic response/request models
  routers/
    __init__.py
    overview.py        # GET /api/status, /api/overview
    conversations.py   # GET /api/conversations, /api/conversations/{call_id}
    clusters.py        # GET /api/clusters
    review_queue.py     # GET/POST /api/review-queue...
    fix_workbench.py    # GET/POST /api/fix-workbench...
    jobs.py             # GET/POST /api/jobs...
tests/api/
  __init__.py
  conftest.py          # db_session + client fixtures (dependency override)
  test_main.py
  test_overview.py
  test_conversations.py
  test_clusters.py
  test_review_queue.py
  test_fix_workbench.py
  test_jobs.py

frontend/
  package.json, tsconfig.json, vite.config.ts, index.html
  src/
    main.tsx, App.tsx, router.tsx
    styles/tokens.css, global.css
    context/RoleContext.tsx
    constants.ts
    api/client.ts
    components/
      Card.tsx, SeverityBadge.tsx, DimensionDots.tsx, StatTile.tsx,
      Skeleton.tsx, Pagination.tsx, Table.tsx, Modal.tsx, Tabs.tsx
    routes/
      Overview.tsx, Conversations.tsx, CallDetail.tsx, Clusters.tsx,
      ReviewQueue.tsx, FixWorkbench.tsx, Jobs.tsx

agentlens/dashboard/
  data.py            # UNCHANGED
  app.py, ui.py, pages/*.py   # REMOVED in the final task, once frontend verified
pyproject.toml        # streamlit dependency removed in the final task
```

---

## Task 1: FastAPI app skeleton + DB dependency + health check

**Files:**
- Create: `agentlens/api/__init__.py` (empty)
- Create: `agentlens/api/deps.py`
- Create: `agentlens/api/main.py`
- Create: `tests/api/__init__.py` (empty)
- Create: `tests/api/conftest.py`
- Create: `tests/api/test_main.py`

**Interfaces:**
- Produces: `agentlens.api.deps.get_db() -> Iterator[Session]` (FastAPI dependency), `agentlens.api.main.app: FastAPI`, `agentlens.api.main.create_app() -> FastAPI`.
- Consumes: `agentlens.db.open_session()` (existing).

- [ ] **Step 1: Write the failing test**

```python
# tests/api/test_main.py
"""Smoke test for the FastAPI app factory and health endpoint."""

from fastapi.testclient import TestClient

from agentlens.api.main import app


def test_health_returns_ok() -> None:
    client = TestClient(app)
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/api/test_main.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'agentlens.api'`

- [ ] **Step 3: Write `deps.py`**

```python
# agentlens/api/deps.py
"""FastAPI dependency providing a DB session per request."""

from collections.abc import Iterator

from sqlalchemy.orm import Session

from agentlens.db import open_session


def get_db() -> Iterator[Session]:
    """Yield a session for the request lifetime, closing it afterward."""
    session = open_session()
    try:
        yield session
    finally:
        session.close()
```

- [ ] **Step 4: Write `main.py`**

```python
# agentlens/api/main.py
"""FastAPI app factory: CORS for the local Vite dev server, router mounts."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from agentlens.api.routers import (
    clusters,
    conversations,
    fix_workbench,
    jobs,
    overview,
    review_queue,
)


def create_app() -> FastAPI:
    """Build the AgentLens API app with all routers mounted under /api."""
    app = FastAPI(title="AgentLens API")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(overview.router, prefix="/api")
    app.include_router(conversations.router, prefix="/api")
    app.include_router(clusters.router, prefix="/api")
    app.include_router(review_queue.router, prefix="/api")
    app.include_router(fix_workbench.router, prefix="/api")
    app.include_router(jobs.router, prefix="/api")
    return app


app = create_app()
```

- [ ] **Step 5: Create empty router package and stub routers so imports resolve**

```python
# agentlens/api/routers/__init__.py
```

```python
# agentlens/api/routers/overview.py
"""Placeholder — replaced with real endpoints in Task 3."""

from fastapi import APIRouter

router = APIRouter(tags=["overview"])
```

Create the same one-line placeholder (`router = APIRouter(tags=["<name>"])`) in `agentlens/api/routers/conversations.py`, `clusters.py`, `review_queue.py`, `fix_workbench.py`, and `jobs.py`, each with its own `tags=[...]`.

- [ ] **Step 6: Write the `conftest.py` fixtures used by every later router test**

```python
# tests/api/conftest.py
"""Shared FastAPI test fixtures: an isolated DB session wired into the app."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from agentlens.api.deps import get_db
from agentlens.api.main import app
from agentlens.models import Base


@pytest.fixture()
def db_session(tmp_path: "pytest.TempPathFactory") -> Iterator[Session]:
    """A Session bound to a fresh file-backed SQLite database in tmp_path."""
    engine = create_engine(f"sqlite:///{tmp_path}/test.db")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture()
def client(db_session: Session) -> Iterator[TestClient]:
    """A TestClient whose get_db dependency is overridden to use db_session."""

    def _override() -> Iterator[Session]:
        yield db_session

    app.dependency_overrides[get_db] = _override
    yield TestClient(app)
    app.dependency_overrides.clear()
```

Note: `tmp_path` is a `pathlib.Path` fixture built into pytest; the type hint above is illustrative only — pytest injects it automatically, so leave the parameter unannotated in the actual file (`def db_session(tmp_path):`) to avoid importing a nonexistent `pytest.TempPathFactory` type. Use:

```python
def db_session(tmp_path):  # type: ignore[no-untyped-def]
```

if `mypy --strict` complains about the missing annotation; otherwise annotate as `tmp_path: Path` with `from pathlib import Path`.

- [ ] **Step 7: Run test to verify it passes**

Run: `uv run pytest tests/api/test_main.py -v`
Expected: PASS

- [ ] **Step 8: Type-check and lint**

Run: `uv run mypy agentlens/api/ && uv run ruff check agentlens/api/ tests/api/`
Expected: no errors

- [ ] **Step 9: Commit**

```bash
git add agentlens/api tests/api
git commit -m "feat: FastAPI app skeleton with health check (docs/superpowers/plans/2026-07-13-streamlit-to-web-migration.md)"
```

---

## Task 2: Pydantic response/request schemas

**Files:**
- Create: `agentlens/api/schemas.py`

**Interfaces:**
- Consumes: dataclasses from `agentlens/dashboard/data.py` (`StatusSummary`, `ConversationRow`, `ClusterCard`, `DimensionQuality`, `CostTotals`, `CallDetailData`), ORM models from `agentlens/models.py` (`EvalRecord`, `DeterministicCheckResult`, `Cluster`, `GroundTruthLabel`, `FixProposal`, `RegressionRun`, `JobRun`), `agentlens.feedback.calibration.AgreementStats`.
- Produces: every schema class listed below, importable as `from agentlens.api.schemas import ...` — later tasks depend on these exact names and field names.

- [ ] **Step 1: Write the schemas file directly (pure data classes — no separate "test" beyond mypy/import, verified in Step 2)**

```python
# agentlens/api/schemas.py
"""Pydantic response/request models.

Every *_Out model sets from_attributes=True so FastAPI can validate the
dataclass or ORM instances returned by dashboard/data.py and the
business-logic modules directly (no hand-copied field mapping needed for
flat shapes); composed shapes (e.g. CallDetailOut) are still built field by
field in the router because their source objects nest differently than the
response shape.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class StatusSummaryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    last_eval_at: datetime | None
    n_calls: int
    n_golden: int


class ConversationRowOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    call_id: str
    scenario: str
    failed_dimensions: set[str]
    has_p0: bool
    avg_score: float
    est_cost_cents: float
    created_at: datetime


class ClusterLabelOut(BaseModel):
    id: int
    label: str


class ConversationsListOut(BaseModel):
    rows: list[ConversationRowOut]
    total: int
    clusters: list[ClusterLabelOut]


class ClusterCardOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    cluster_id: int
    label: str
    description: str
    routing: str
    severity: str
    size: int
    is_p0: bool


class ClustersListOut(BaseModel):
    cards: list[ClusterCardOut]
    n_failures: int
    last_clustered_at: datetime | None


class DimensionQualityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    pass_rate: float
    delta: float | None


class OverviewOut(BaseModel):
    quality: dict[str, DimensionQualityOut]
    severities: dict[str, int]
    precision: float | None
    recall: float | None
    agreement: float | None
    n_reviews: int
    top_clusters: list[ClusterCardOut]
    total_eval_cents: float
    avg_per_call_cents: float


class EvalRecordOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    dimension: str
    score: int
    severity: str
    passed: bool
    failure_description: str | None
    judge_reasoning: str
    pipeline_stage: str | None
    judge_model: str
    prompt_version: str
    rubric_version: str
    input_hash: str


class CheckResultOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    check_name: str
    triggered: bool
    detail: str | None


class ClusterRefOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    label: str


class GroundTruthOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    failure_mode: str
    pipeline_stage: str
    severity: str


class CallDetailOut(BaseModel):
    call_id: str
    scenario: str
    transcript: list[dict[str, Any]]
    records: list[EvalRecordOut]
    checks: list[CheckResultOut]
    cluster: ClusterRefOut | None
    ground_truth: GroundTruthOut | None


class AgreementStatsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    n_reviews: int
    n_agree: int
    agreement: float
    per_dimension: dict[str, float]
    per_dimension_counts: dict[str, int]


class FindingOut(BaseModel):
    eval_record_id: int
    call_id: str
    scenario: str
    dimension: str
    score: int
    severity: str
    failure_description: str | None
    checks: list[CheckResultOut]
    transcript: list[dict[str, Any]]


class ReviewQueueOut(BaseModel):
    stats: AgreementStatsOut
    pending_count: int
    current: FindingOut | None


class SubmitReviewIn(BaseModel):
    verdict: str
    note: str | None = None


class FixProposalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    cluster_id: int
    fix_type: str
    rationale: str
    patch: str
    status: str


class RegressionRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    fix_proposal_id: int
    batch_id: str
    n_before: int
    n_after: int
    before_pass_rates: dict[str, float]
    after_pass_rates: dict[str, float]
    target_dimension: str
    regressed_dimensions: list[str]


class FixWorkbenchOut(BaseModel):
    cluster: ClusterCardOut
    fix: FixProposalOut | None
    regression: RegressionRunOut | None


class JobSummaryOut(BaseModel):
    finished_at: datetime | None
    summary: dict[str, Any]


class JobsStatusOut(BaseModel):
    corpus: JobSummaryOut
    evals: JobSummaryOut
    cluster: JobSummaryOut
    log_lines: list[str]


class EvalEstimateOut(BaseModel):
    n_calls: int
    estimate_cents: float


class GenerateCorpusIn(BaseModel):
    count: int
    failure_rate: float


class RunEvalsIn(BaseModel):
    scope: str
    model: str
```

- [ ] **Step 2: Type-check and import-check**

Run: `uv run mypy agentlens/api/schemas.py && uv run python -c "import agentlens.api.schemas"`
Expected: no errors, no output (successful import)

- [ ] **Step 3: Commit**

```bash
git add agentlens/api/schemas.py
git commit -m "feat: API response/request schemas (docs/superpowers/plans/2026-07-13-streamlit-to-web-migration.md)"
```

---

## Task 3: Overview router (`/api/status`, `/api/overview`)

**Files:**
- Modify: `agentlens/api/routers/overview.py`
- Create: `tests/api/test_overview.py`

**Interfaces:**
- Consumes: `agentlens.dashboard.data.{status_summary, cluster_cards, cost_totals, last_job_run, quality_panel, severity_counts}`, `agentlens.feedback.calibration.compute_agreement`, schemas from Task 2.
- Produces: `GET /api/status -> StatusSummaryOut`, `GET /api/overview -> OverviewOut`.

- [ ] **Step 1: Write the failing test**

```python
# tests/api/test_overview.py
"""Overview and status endpoints."""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from agentlens.models import Call


def test_status_empty_db(client: TestClient) -> None:
    response = client.get("/api/status")
    assert response.status_code == 200
    body = response.json()
    assert body == {"last_eval_at": None, "n_calls": 0, "n_golden": 0}


def test_status_counts_calls(client: TestClient, db_session: Session) -> None:
    db_session.add(Call(id="call_1", scenario="symptom_triage", transcript=[], batch_id="b1"))
    db_session.add(
        Call(
            id="call_2",
            scenario="symptom_triage",
            transcript=[],
            batch_id="b1",
            is_golden=True,
        )
    )
    db_session.commit()

    response = client.get("/api/status")
    body = response.json()
    assert body["n_calls"] == 2
    assert body["n_golden"] == 1


def test_overview_shape_on_empty_db(client: TestClient) -> None:
    response = client.get("/api/overview")
    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {
        "quality",
        "severities",
        "precision",
        "recall",
        "agreement",
        "n_reviews",
        "top_clusters",
        "total_eval_cents",
        "avg_per_call_cents",
    }
    assert body["n_reviews"] == 0
    assert body["top_clusters"] == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/api/test_overview.py -v`
Expected: FAIL — 404s from the placeholder router (no routes defined yet)

- [ ] **Step 3: Implement the router**

```python
# agentlens/api/routers/overview.py
"""GET /api/status and /api/overview — sidebar status block and landing page."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from agentlens.api.deps import get_db
from agentlens.api.schemas import OverviewOut, StatusSummaryOut
from agentlens.dashboard.data import (
    cluster_cards,
    cost_totals,
    last_job_run,
    quality_panel,
    severity_counts,
    status_summary,
)
from agentlens.feedback.calibration import compute_agreement

router = APIRouter(tags=["overview"])


@router.get("/status", response_model=StatusSummaryOut)
def get_status(session: Session = Depends(get_db)) -> StatusSummaryOut:
    return StatusSummaryOut.model_validate(status_summary(session))


@router.get("/overview", response_model=OverviewOut)
def get_overview(session: Session = Depends(get_db)) -> OverviewOut:
    quality = quality_panel(session)
    severities = severity_counts(session)
    agreement = compute_agreement(session)
    metrics_run = last_job_run(session, "judge_metrics")
    top = cluster_cards(session)[:5]
    costs = cost_totals(session)
    summary = metrics_run.summary if metrics_run else {}
    return OverviewOut(
        quality=dict(quality),
        severities=severities,
        precision=summary.get("precision"),
        recall=summary.get("recall"),
        agreement=agreement.agreement if agreement.n_reviews else None,
        n_reviews=agreement.n_reviews,
        top_clusters=list(top),
        total_eval_cents=costs.total_eval_cents,
        avg_per_call_cents=costs.avg_per_call_cents,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/api/test_overview.py -v`
Expected: PASS

- [ ] **Step 5: Type-check and lint**

Run: `uv run mypy agentlens/api/ && uv run ruff check agentlens/api/ tests/api/`
Expected: no errors

- [ ] **Step 6: Commit**

```bash
git add agentlens/api/routers/overview.py tests/api/test_overview.py
git commit -m "feat: overview and status API endpoints (docs/superpowers/plans/2026-07-13-streamlit-to-web-migration.md)"
```

---

## Task 4: Conversations router (list + detail)

**Files:**
- Modify: `agentlens/api/routers/conversations.py`
- Create: `tests/api/test_conversations.py`

**Interfaces:**
- Consumes: `agentlens.dashboard.data.{conversation_rows, call_detail}`, `agentlens.models.Cluster`.
- Produces: `GET /api/conversations -> ConversationsListOut`, `GET /api/conversations/{call_id} -> CallDetailOut` (404 if missing).

- [ ] **Step 1: Write the failing test**

```python
# tests/api/test_conversations.py
"""Conversations list and detail endpoints."""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from agentlens.models import Call, EvalRecord


def _seed_call(session: Session, call_id: str) -> None:
    session.add(
        Call(
            id=call_id,
            scenario="symptom_triage",
            transcript=[{"speaker": "patient", "text": "hi"}],
            batch_id="b1",
        )
    )
    session.add(
        EvalRecord(
            call_id=call_id,
            dimension="safety_compliance",
            score=40,
            severity="P0",
            passed=False,
            failure_description="missed escalation",
            judge_reasoning="reasoning text",
            judge_model="claude-haiku-4-5",
            prompt_version="v1",
            rubric_version="v1",
            input_hash="abc123",
        )
    )
    session.commit()


def test_list_conversations_empty(client: TestClient) -> None:
    response = client.get("/api/conversations")
    assert response.status_code == 200
    body = response.json()
    assert body == {"rows": [], "total": 0, "clusters": []}


def test_list_conversations_returns_seeded_call(client: TestClient, db_session: Session) -> None:
    _seed_call(db_session, "call_1")

    response = client.get("/api/conversations")
    body = response.json()
    assert body["total"] == 1
    assert body["rows"][0]["call_id"] == "call_1"
    assert body["rows"][0]["has_p0"] is True


def test_get_conversation_detail_not_found(client: TestClient) -> None:
    response = client.get("/api/conversations/does_not_exist")
    assert response.status_code == 404


def test_get_conversation_detail_found(client: TestClient, db_session: Session) -> None:
    _seed_call(db_session, "call_1")

    response = client.get("/api/conversations/call_1")
    assert response.status_code == 200
    body = response.json()
    assert body["call_id"] == "call_1"
    assert body["records"][0]["dimension"] == "safety_compliance"
    assert body["cluster"] is None
    assert body["ground_truth"] is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/api/test_conversations.py -v`
Expected: FAIL — 404s from the placeholder router

- [ ] **Step 3: Implement the router**

```python
# agentlens/api/routers/conversations.py
"""GET /api/conversations (list) and /api/conversations/{call_id} (detail)."""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from agentlens.api.deps import get_db
from agentlens.api.schemas import (
    CallDetailOut,
    CheckResultOut,
    ClusterLabelOut,
    ClusterRefOut,
    ConversationsListOut,
    EvalRecordOut,
    GroundTruthOut,
)
from agentlens.dashboard.data import call_detail, conversation_rows
from agentlens.models import Cluster

router = APIRouter(tags=["conversations"])

_PAGE_SIZE = 25


@router.get("/conversations", response_model=ConversationsListOut)
def list_conversations(
    severity: str | None = Query(default=None),
    dimension: str | None = Query(default=None),
    cluster_id: int | None = Query(default=None),
    outcome: Literal["pass", "fail"] | None = Query(default=None),
    page: int = Query(default=0, ge=0),
    session: Session = Depends(get_db),
) -> ConversationsListOut:
    rows = conversation_rows(
        session, severity=severity, dimension=dimension, cluster_id=cluster_id, outcome=outcome
    )
    clusters = session.query(Cluster).order_by(Cluster.label).all()
    visible = rows[page * _PAGE_SIZE : (page + 1) * _PAGE_SIZE]
    return ConversationsListOut(
        rows=list(visible),
        total=len(rows),
        clusters=[ClusterLabelOut(id=c.id, label=c.label) for c in clusters],
    )


@router.get("/conversations/{call_id}", response_model=CallDetailOut)
def get_conversation(call_id: str, session: Session = Depends(get_db)) -> CallDetailOut:
    detail = call_detail(session, call_id)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"call {call_id!r} not found")
    return CallDetailOut(
        call_id=detail.call.id,
        scenario=detail.call.scenario,
        transcript=detail.call.transcript,
        records=[EvalRecordOut.model_validate(r) for r in detail.records],
        checks=[CheckResultOut.model_validate(c) for c in detail.checks],
        cluster=ClusterRefOut(id=detail.cluster.id, label=detail.cluster.label)
        if detail.cluster is not None
        else None,
        ground_truth=GroundTruthOut.model_validate(detail.ground_truth)
        if detail.ground_truth is not None
        else None,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/api/test_conversations.py -v`
Expected: PASS

- [ ] **Step 5: Type-check and lint**

Run: `uv run mypy agentlens/api/ && uv run ruff check agentlens/api/ tests/api/`
Expected: no errors

- [ ] **Step 6: Commit**

```bash
git add agentlens/api/routers/conversations.py tests/api/test_conversations.py
git commit -m "feat: conversations list and detail API endpoints (docs/superpowers/plans/2026-07-13-streamlit-to-web-migration.md)"
```

---

## Task 5: Clusters router

**Files:**
- Modify: `agentlens/api/routers/clusters.py`
- Create: `tests/api/test_clusters.py`

**Interfaces:**
- Consumes: `agentlens.dashboard.data.{cluster_cards, last_job_run}`.
- Produces: `GET /api/clusters -> ClustersListOut`.

- [ ] **Step 1: Write the failing test**

```python
# tests/api/test_clusters.py
"""Clusters list endpoint."""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from agentlens.models import Cluster


def test_list_clusters_empty(client: TestClient) -> None:
    response = client.get("/api/clusters")
    assert response.status_code == 200
    assert response.json() == {"cards": [], "n_failures": 0, "last_clustered_at": None}


def test_list_clusters_returns_seeded_cluster(client: TestClient, db_session: Session) -> None:
    db_session.add(
        Cluster(
            label="Missed escalations",
            description="Agent fails to escalate red-flag symptoms.",
            routing_suggestion="prompt_fix",
            dominant_severity="P0",
            size=3,
        )
    )
    db_session.commit()

    response = client.get("/api/clusters")
    body = response.json()
    assert body["n_failures"] == 3
    assert body["cards"][0]["label"] == "Missed escalations"
    assert body["cards"][0]["is_p0"] is True


def test_list_clusters_filters_by_severity(client: TestClient, db_session: Session) -> None:
    db_session.add(
        Cluster(
            label="P1 cluster",
            description="",
            routing_suggestion="ops_process",
            dominant_severity="P1",
            size=2,
        )
    )
    db_session.commit()

    response = client.get("/api/clusters", params={"severity": "P0"})
    assert response.json()["cards"] == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/api/test_clusters.py -v`
Expected: FAIL — 404s from the placeholder router

- [ ] **Step 3: Implement the router**

```python
# agentlens/api/routers/clusters.py
"""GET /api/clusters — recurring failure patterns."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from agentlens.api.deps import get_db
from agentlens.api.schemas import ClustersListOut
from agentlens.dashboard.data import cluster_cards, last_job_run

router = APIRouter(tags=["clusters"])


@router.get("/clusters", response_model=ClustersListOut)
def list_clusters(
    routing: str | None = Query(default=None),
    severity: str | None = Query(default=None),
    focus_id: int | None = Query(default=None),
    session: Session = Depends(get_db),
) -> ClustersListOut:
    cards = cluster_cards(session, routing=routing, severity=severity)
    if focus_id is not None:
        cards = [c for c in cards if c.cluster_id == focus_id]
    last_run = last_job_run(session, "recluster")
    return ClustersListOut(
        cards=list(cards),
        n_failures=sum(c.size for c in cards),
        last_clustered_at=last_run.finished_at if last_run else None,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/api/test_clusters.py -v`
Expected: PASS

- [ ] **Step 5: Type-check and lint**

Run: `uv run mypy agentlens/api/ && uv run ruff check agentlens/api/ tests/api/`
Expected: no errors

- [ ] **Step 6: Commit**

```bash
git add agentlens/api/routers/clusters.py tests/api/test_clusters.py
git commit -m "feat: clusters list API endpoint (docs/superpowers/plans/2026-07-13-streamlit-to-web-migration.md)"
```

---

## Task 6: Review Queue router

**Files:**
- Modify: `agentlens/api/routers/review_queue.py`
- Create: `tests/api/test_review_queue.py`

**Interfaces:**
- Consumes: `agentlens.feedback.calibration.compute_agreement`, `agentlens.feedback.queue.{review_queue, submit_review}`.
- Produces: `GET /api/review-queue -> ReviewQueueOut`, `POST /api/review-queue/{eval_record_id} -> ReviewQueueOut` (body: `SubmitReviewIn`; 400 on invalid verdict).

- [ ] **Step 1: Write the failing test**

```python
# tests/api/test_review_queue.py
"""Review queue GET and POST endpoints."""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from agentlens.models import Call, EvalRecord


def _seed_finding(session: Session) -> int:
    session.add(
        Call(id="call_1", scenario="symptom_triage", transcript=[{"speaker": "a", "text": "x"}], batch_id="b1")
    )
    record = EvalRecord(
        call_id="call_1",
        dimension="safety_compliance",
        score=20,
        severity="P0",
        passed=False,
        failure_description="missed escalation",
        judge_reasoning="reasoning",
        judge_model="claude-haiku-4-5",
        prompt_version="v1",
        rubric_version="v1",
        input_hash="abc123",
    )
    session.add(record)
    session.commit()
    return record.id


def test_empty_queue(client: TestClient) -> None:
    response = client.get("/api/review-queue")
    body = response.json()
    assert body["pending_count"] == 0
    assert body["current"] is None


def test_queue_returns_pending_finding(client: TestClient, db_session: Session) -> None:
    _seed_finding(db_session)

    response = client.get("/api/review-queue")
    body = response.json()
    assert body["pending_count"] == 1
    assert body["current"]["call_id"] == "call_1"
    assert body["current"]["dimension"] == "safety_compliance"


def test_submit_review_advances_queue(client: TestClient, db_session: Session) -> None:
    record_id = _seed_finding(db_session)

    response = client.post(
        f"/api/review-queue/{record_id}", json={"verdict": "agree", "note": "looks right"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["pending_count"] == 0
    assert body["stats"]["n_reviews"] == 1


def test_submit_review_rejects_invalid_verdict(client: TestClient, db_session: Session) -> None:
    record_id = _seed_finding(db_session)

    response = client.post(f"/api/review-queue/{record_id}", json={"verdict": "maybe"})
    assert response.status_code == 400
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/api/test_review_queue.py -v`
Expected: FAIL — 404s from the placeholder router

- [ ] **Step 3: Implement the router**

```python
# agentlens/api/routers/review_queue.py
"""GET /api/review-queue and POST /api/review-queue/{eval_record_id} — human calibration."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from agentlens.api.deps import get_db
from agentlens.api.schemas import (
    AgreementStatsOut,
    CheckResultOut,
    FindingOut,
    ReviewQueueOut,
    SubmitReviewIn,
)
from agentlens.feedback.calibration import compute_agreement
from agentlens.feedback.queue import review_queue, submit_review

router = APIRouter(tags=["review-queue"])


def _current_queue(session: Session) -> ReviewQueueOut:
    stats = compute_agreement(session)
    queue = review_queue(session)
    pending = [r for r in queue if r.review is None]
    current = None
    if pending:
        finding = pending[0]
        current = FindingOut(
            eval_record_id=finding.id,
            call_id=finding.call.id,
            scenario=finding.call.scenario,
            dimension=finding.dimension,
            score=finding.score,
            severity=finding.severity,
            failure_description=finding.failure_description,
            checks=[CheckResultOut.model_validate(c) for c in finding.call.check_results],
            transcript=finding.call.transcript,
        )
    return ReviewQueueOut(
        stats=AgreementStatsOut.model_validate(stats),
        pending_count=len(pending),
        current=current,
    )


@router.get("/review-queue", response_model=ReviewQueueOut)
def get_review_queue(session: Session = Depends(get_db)) -> ReviewQueueOut:
    return _current_queue(session)


@router.post("/review-queue/{eval_record_id}", response_model=ReviewQueueOut)
def post_review(
    eval_record_id: int, body: SubmitReviewIn, session: Session = Depends(get_db)
) -> ReviewQueueOut:
    if body.verdict not in ("agree", "disagree"):
        raise HTTPException(status_code=400, detail="verdict must be 'agree' or 'disagree'")
    submit_review(session, eval_record_id, body.verdict, body.note)  # type: ignore[arg-type]
    session.commit()
    return _current_queue(session)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/api/test_review_queue.py -v`
Expected: PASS

- [ ] **Step 5: Type-check and lint**

Run: `uv run mypy agentlens/api/ && uv run ruff check agentlens/api/ tests/api/`
Expected: no errors

- [ ] **Step 6: Commit**

```bash
git add agentlens/api/routers/review_queue.py tests/api/test_review_queue.py
git commit -m "feat: review queue API endpoints (docs/superpowers/plans/2026-07-13-streamlit-to-web-migration.md)"
```

---

## Task 7: Fix Workbench router

**Files:**
- Modify: `agentlens/api/routers/fix_workbench.py`
- Create: `tests/api/test_fix_workbench.py`

**Interfaces:**
- Consumes: `agentlens.dashboard.data.{cluster_cards, latest_fix, latest_regression}`, `agentlens.fixes.propose.propose_fix`, `agentlens.fixes.regression.regenerate_for_fix`, `agentlens.fixes.report.build_regression_run`, `agentlens.evals.runner.evaluate_call`.
- Produces: `GET /api/fix-workbench/clusters -> list[ClusterLabelOut]`, `GET /api/fix-workbench/{cluster_id} -> FixWorkbenchOut`, `POST /api/fix-workbench/{cluster_id}/generate -> FixProposalOut`, `POST /api/fix-workbench/{cluster_id}/apply-regression -> RegressionRunOut`.

This task's mutation endpoints call the Anthropic API through `propose_fix`/`regenerate_for_fix` — the tests below cover the deterministic parts (cluster lookup, P0 gating, 404s) without invoking `/generate` or `/apply-regression` against a live model; those two endpoints are exercised manually in Task 18's end-to-end check, matching how the Streamlit version never had automated coverage for its LLM-calling buttons either.

- [ ] **Step 1: Write the failing test**

```python
# tests/api/test_fix_workbench.py
"""Fix Workbench endpoints: cluster listing, lookup, and P0/404 guards."""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from agentlens.models import Cluster


def test_list_selectable_clusters_excludes_p0(client: TestClient, db_session: Session) -> None:
    db_session.add(
        Cluster(label="P0 cluster", description="", routing_suggestion="prompt_fix",
                 dominant_severity="P0", size=1)
    )
    db_session.add(
        Cluster(label="P1 cluster", description="", routing_suggestion="prompt_fix",
                 dominant_severity="P1", size=2)
    )
    db_session.commit()

    response = client.get("/api/fix-workbench/clusters")
    labels = [c["label"] for c in response.json()]
    assert labels == ["P1 cluster"]


def test_get_fix_workbench_not_found(client: TestClient) -> None:
    response = client.get("/api/fix-workbench/999")
    assert response.status_code == 404


def test_get_fix_workbench_no_fix_yet(client: TestClient, db_session: Session) -> None:
    cluster = Cluster(
        label="P1 cluster", description="d", routing_suggestion="prompt_fix",
        dominant_severity="P1", size=2,
    )
    db_session.add(cluster)
    db_session.commit()

    response = client.get(f"/api/fix-workbench/{cluster.id}")
    body = response.json()
    assert body["fix"] is None
    assert body["regression"] is None
    assert body["cluster"]["label"] == "P1 cluster"


def test_apply_regression_blocked_on_p0_cluster(client: TestClient, db_session: Session) -> None:
    cluster = Cluster(
        label="P0 cluster", description="", routing_suggestion="prompt_fix",
        dominant_severity="P0", size=1,
    )
    db_session.add(cluster)
    db_session.commit()

    response = client.post(f"/api/fix-workbench/{cluster.id}/apply-regression")
    assert response.status_code == 400


def test_apply_regression_requires_a_fix(client: TestClient, db_session: Session) -> None:
    cluster = Cluster(
        label="P1 cluster", description="", routing_suggestion="prompt_fix",
        dominant_severity="P1", size=1,
    )
    db_session.add(cluster)
    db_session.commit()

    response = client.post(f"/api/fix-workbench/{cluster.id}/apply-regression")
    assert response.status_code == 400
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/api/test_fix_workbench.py -v`
Expected: FAIL — 404s from the placeholder router

- [ ] **Step 3: Implement the router**

```python
# agentlens/api/routers/fix_workbench.py
"""Fix Workbench endpoints: propose a fix, apply it, run regression."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from agentlens.api.deps import get_db
from agentlens.api.schemas import (
    ClusterLabelOut,
    FixProposalOut,
    FixWorkbenchOut,
    RegressionRunOut,
)
from agentlens.dashboard.data import cluster_cards, latest_fix, latest_regression
from agentlens.evals.runner import evaluate_call
from agentlens.fixes.propose import propose_fix
from agentlens.fixes.regression import regenerate_for_fix
from agentlens.fixes.report import build_regression_run
from agentlens.models import Cluster, FixProposal

router = APIRouter(tags=["fix-workbench"])


@router.get("/fix-workbench/clusters", response_model=list[ClusterLabelOut])
def list_selectable_clusters(session: Session = Depends(get_db)) -> list[ClusterLabelOut]:
    return [
        ClusterLabelOut(id=c.cluster_id, label=c.label)
        for c in cluster_cards(session)
        if not c.is_p0
    ]


def _get_cluster(session: Session, cluster_id: int) -> Cluster:
    cluster = session.get(Cluster, cluster_id)
    if cluster is None:
        raise HTTPException(status_code=404, detail=f"cluster {cluster_id} not found")
    return cluster


@router.get("/fix-workbench/{cluster_id}", response_model=FixWorkbenchOut)
def get_fix_workbench(cluster_id: int, session: Session = Depends(get_db)) -> FixWorkbenchOut:
    cluster = _get_cluster(session, cluster_id)
    fix = latest_fix(session, cluster_id)
    regression = latest_regression(session, fix.id) if fix is not None else None
    card = next(c for c in cluster_cards(session) if c.cluster_id == cluster_id)
    return FixWorkbenchOut(
        cluster=card,
        fix=FixProposalOut.model_validate(fix) if fix is not None else None,
        regression=RegressionRunOut.model_validate(regression) if regression is not None else None,
    )


@router.post("/fix-workbench/{cluster_id}/generate", response_model=FixProposalOut)
def generate_fix(cluster_id: int, session: Session = Depends(get_db)) -> FixProposalOut:
    cluster = _get_cluster(session, cluster_id)
    result = propose_fix(session, cluster)
    if not result.success or result.parsed is None:
        raise HTTPException(status_code=422, detail=f"fix generation failed: {result.error}")
    fix = FixProposal(
        cluster_id=cluster.id,
        fix_type=result.parsed.fix_type,
        rationale=result.parsed.rationale,
        patch=result.parsed.patch,
    )
    session.add(fix)
    session.commit()
    return FixProposalOut.model_validate(fix)


@router.post("/fix-workbench/{cluster_id}/apply-regression", response_model=RegressionRunOut)
def apply_regression(cluster_id: int, session: Session = Depends(get_db)) -> RegressionRunOut:
    cluster = _get_cluster(session, cluster_id)
    if cluster.dominant_severity == "P0":
        raise HTTPException(
            status_code=400,
            detail="P0 findings require human acknowledgment before regression can run",
        )
    fix = latest_fix(session, cluster_id)
    if fix is None:
        raise HTTPException(status_code=400, detail="no fix proposed yet for this cluster")
    regenerated = regenerate_for_fix(session, fix)
    for call in regenerated:
        evaluate_call(session, call)
    run = build_regression_run(session, fix, regenerated)
    session.commit()
    return RegressionRunOut.model_validate(run)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/api/test_fix_workbench.py -v`
Expected: PASS

- [ ] **Step 5: Type-check and lint**

Run: `uv run mypy agentlens/api/ && uv run ruff check agentlens/api/ tests/api/`
Expected: no errors

- [ ] **Step 6: Commit**

```bash
git add agentlens/api/routers/fix_workbench.py tests/api/test_fix_workbench.py
git commit -m "feat: fix workbench API endpoints (docs/superpowers/plans/2026-07-13-streamlit-to-web-migration.md)"
```

---

## Task 8: Jobs router

**Files:**
- Modify: `agentlens/api/routers/jobs.py`
- Create: `tests/api/test_jobs.py`

**Interfaces:**
- Consumes: `agentlens.dashboard.data.{last_job_run, n_calls_for_scope, tail_log}`, `agentlens.config.get_settings`, `agentlens.llm.gateway.cost_cents`.
- Produces: `GET /api/jobs/status -> JobsStatusOut`, `GET /api/jobs/eval-estimate -> EvalEstimateOut`, `POST /api/jobs/corpus`, `POST /api/jobs/evals`, `POST /api/jobs/recluster` (all three return `{"status": "started"}`, HTTP 202).

The three POST endpoints launch a real `subprocess.Popen` exactly as the Streamlit "Jobs" page did; the test below monkeypatches `subprocess.Popen` so tests don't spawn real batch jobs.

- [ ] **Step 1: Write the failing test**

```python
# tests/api/test_jobs.py
"""Jobs status, eval-estimate, and job-launch endpoints."""

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient


def test_jobs_status_empty_db(client: TestClient) -> None:
    response = client.get("/api/jobs/status")
    assert response.status_code == 200
    body = response.json()
    assert body["corpus"] == {"finished_at": None, "summary": {}}
    assert body["log_lines"] == []


def test_eval_estimate_empty_db(client: TestClient) -> None:
    response = client.get(
        "/api/jobs/eval-estimate", params={"scope": "full", "model": "claude-haiku-4-5"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["n_calls"] == 0
    assert body["estimate_cents"] == 0.0


def test_launch_corpus_starts_subprocess(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    mock_popen = MagicMock()
    monkeypatch.setattr("agentlens.api.routers.jobs.subprocess.Popen", mock_popen)

    response = client.post("/api/jobs/corpus", json={"count": 10, "failure_rate": 0.3})
    assert response.status_code == 202
    assert response.json() == {"status": "started"}
    mock_popen.assert_called_once()
    args = mock_popen.call_args[0][0]
    assert "agentlens.jobs.generate_corpus" in args


def test_launch_evals_starts_subprocess(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    mock_popen = MagicMock()
    monkeypatch.setattr("agentlens.api.routers.jobs.subprocess.Popen", mock_popen)

    response = client.post(
        "/api/jobs/evals", json={"scope": "unevaluated", "model": "claude-haiku-4-5"}
    )
    assert response.status_code == 202
    mock_popen.assert_called_once()


def test_launch_recluster_starts_subprocess(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    mock_popen = MagicMock()
    monkeypatch.setattr("agentlens.api.routers.jobs.subprocess.Popen", mock_popen)

    response = client.post("/api/jobs/recluster")
    assert response.status_code == 202
    mock_popen.assert_called_once()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/api/test_jobs.py -v`
Expected: FAIL — 404s from the placeholder router

- [ ] **Step 3: Implement the router**

```python
# agentlens/api/routers/jobs.py
"""Jobs endpoints: launch batch jobs, report their status, tail the job log."""

import subprocess
import sys
from typing import Literal

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from agentlens.api.deps import get_db
from agentlens.api.schemas import (
    EvalEstimateOut,
    GenerateCorpusIn,
    JobSummaryOut,
    JobsStatusOut,
    RunEvalsIn,
)
from agentlens.config import get_settings
from agentlens.dashboard.data import last_job_run, n_calls_for_scope, tail_log
from agentlens.llm.gateway import cost_cents

router = APIRouter(tags=["jobs"])

_JUDGE_EST_TOKENS = (1200, 500)


def _summary_out(session: Session, job_name: str) -> JobSummaryOut:
    run = last_job_run(session, job_name)
    return JobSummaryOut(
        finished_at=run.finished_at if run else None,
        summary=run.summary if run else {},
    )


@router.get("/jobs/status", response_model=JobsStatusOut)
def jobs_status(session: Session = Depends(get_db)) -> JobsStatusOut:
    return JobsStatusOut(
        corpus=_summary_out(session, "generate_corpus"),
        evals=_summary_out(session, "run_evals"),
        cluster=_summary_out(session, "recluster"),
        log_lines=tail_log(get_settings().jobs_log_path, n=20),
    )


@router.get("/jobs/eval-estimate", response_model=EvalEstimateOut)
def eval_estimate(
    scope: Literal["full", "unevaluated"], model: str, session: Session = Depends(get_db)
) -> EvalEstimateOut:
    n = n_calls_for_scope(session, scope, model)
    return EvalEstimateOut(n_calls=n, estimate_cents=n * cost_cents(model, *_JUDGE_EST_TOKENS))


@router.post("/jobs/corpus", status_code=202)
def launch_corpus(body: GenerateCorpusIn) -> dict[str, str]:
    subprocess.Popen(
        [
            sys.executable,
            "-m",
            "agentlens.jobs.generate_corpus",
            "--count",
            str(body.count),
            "--failure-rate",
            str(body.failure_rate),
        ]
    )
    return {"status": "started"}


@router.post("/jobs/evals", status_code=202)
def launch_evals(body: RunEvalsIn) -> dict[str, str]:
    subprocess.Popen(
        [
            sys.executable,
            "-m",
            "agentlens.jobs.run_evals",
            "--scope",
            body.scope,
            "--model",
            body.model,
        ]
    )
    return {"status": "started"}


@router.post("/jobs/recluster", status_code=202)
def launch_recluster() -> dict[str, str]:
    subprocess.Popen([sys.executable, "-m", "agentlens.jobs.recluster"])
    return {"status": "started"}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/api/test_jobs.py -v`
Expected: PASS

- [ ] **Step 5: Type-check and lint, then run the full backend test suite**

Run: `uv run mypy agentlens/api/ && uv run ruff check agentlens/api/ tests/api/ && uv run pytest tests/api/ -v`
Expected: no errors, all tests pass

- [ ] **Step 6: Commit**

```bash
git add agentlens/api/routers/jobs.py tests/api/test_jobs.py
git commit -m "feat: jobs API endpoints (docs/superpowers/plans/2026-07-13-streamlit-to-web-migration.md)"
```

---

## Task 9: Vite + React + TypeScript scaffold, design tokens

**Files:**
- Create: `frontend/package.json`, `frontend/tsconfig.json`, `frontend/tsconfig.node.json`, `frontend/vite.config.ts`, `frontend/index.html`
- Create: `frontend/src/main.tsx`, `frontend/src/styles/tokens.css`, `frontend/src/styles/global.css`
- Create: `frontend/.gitignore`

**Interfaces:**
- Produces: a running Vite dev server on port 5173 proxying `/api/*` to `http://localhost:8000`; CSS custom properties (`--color-primary`, `--color-panel-tint`, etc.) usable by every later component.

- [ ] **Step 1: Scaffold the Vite project**

```bash
cd /Users/praveendua/Documents/AgenticProjects/agentlens-web
npm create vite@latest frontend -- --template react-ts
```

- [ ] **Step 2: Install dependencies**

```bash
cd frontend
npm install
npm install react-router-dom @tanstack/react-query
```

- [ ] **Step 3: Configure the dev-server proxy**

```typescript
// frontend/vite.config.ts
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": "http://localhost:8000",
    },
  },
});
```

- [ ] **Step 4: Write the design tokens**

```css
/* frontend/src/styles/tokens.css */
:root {
  --color-primary: #0f7864;
  --color-primary-dark: #0b5c4c;
  --color-accent-gradient: linear-gradient(90deg, #8fe388, #2fbfa0);
  --color-panel-tint: #f2f9f6;
  --color-surface: #ffffff;
  --color-border: #e4e4e0;
  --color-text: #1a1d1b;
  --color-text-secondary: #6b706d;

  --severity-p0: #d64545;
  --severity-p1: #c98a1f;
  --severity-p2: #6b7280;

  --tag-mint-bg: #e3f5ef;
  --tag-mint-border: #a9dcc9;
  --tag-amber-bg: #faf1e0;
  --tag-amber-border: #e6c98a;
  --tag-slate-bg: #eef0f2;
  --tag-slate-border: #c7cdd3;

  --radius-card: 12px;
  --radius-button: 8px;
  --space-1: 4px;
  --space-2: 8px;
  --space-3: 16px;
  --space-4: 24px;
  --space-5: 32px;

  --font-family: -apple-system, "SF Pro Text", "SF Pro Display", "Helvetica Neue", Arial,
    sans-serif;
  --font-size-body: 15px;
  --font-size-dense: 14px;
  --line-height-dense: 1.45;
}

@media (prefers-color-scheme: dark) {
  :root {
    --color-surface: #1c1f1e;
    --color-panel-tint: #16211d;
    --color-border: #2c302e;
    --color-text: #f2f4f3;
    --color-text-secondary: #a1a7a4;
  }
}
```

- [ ] **Step 5: Write global element/utility styles**

```css
/* frontend/src/styles/global.css */
@import "./tokens.css";

* {
  box-sizing: border-box;
}

body {
  margin: 0;
  font-family: var(--font-family);
  font-size: var(--font-size-body);
  color: var(--color-text);
  background: var(--color-surface);
}

h1, h2, h3 {
  font-weight: 700;
  letter-spacing: -0.01em;
}

.btn {
  border-radius: var(--radius-button);
  padding: var(--space-2) var(--space-3);
  font-size: var(--font-size-body);
  font-weight: 600;
  border: 1px solid transparent;
  cursor: pointer;
}

.btn-primary {
  background: var(--color-primary);
  color: #fff;
}

.btn-primary:hover {
  background: var(--color-primary-dark);
}

.btn-secondary {
  background: var(--color-surface);
  color: var(--color-primary);
  border-color: var(--color-primary);
}

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.text-dense {
  font-size: var(--font-size-dense);
  line-height: var(--line-height-dense);
  letter-spacing: -0.005em;
}

.numeric {
  font-variant-numeric: tabular-nums;
}
```

- [ ] **Step 6: Wire the tokens into the app entry point**

```tsx
// frontend/src/main.tsx
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "./styles/global.css";
import App from "./App";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>
);
```

- [ ] **Step 7: Verify the dev server starts and type-checks**

Run:
```bash
cd frontend
npm run build
```
Expected: build completes with no TypeScript errors (the default `App.tsx` from the Vite template is replaced in Task 11, so a transient placeholder is fine here as long as it compiles).

- [ ] **Step 8: Commit**

```bash
cd /Users/praveendua/Documents/AgenticProjects/agentlens-web
git add frontend
git commit -m "feat: Vite React TypeScript scaffold with design tokens (docs/superpowers/plans/2026-07-13-streamlit-to-web-migration.md)"
```

---

## Task 10: Core UI components (Card, SeverityBadge, DimensionDots, StatTile, Pagination, Table, Skeleton, Modal, Tabs)

**Files:**
- Create: `frontend/src/components/Card.tsx`
- Create: `frontend/src/components/SeverityBadge.tsx`
- Create: `frontend/src/components/DimensionDots.tsx`
- Create: `frontend/src/components/StatTile.tsx`
- Create: `frontend/src/components/Skeleton.tsx`
- Create: `frontend/src/components/Pagination.tsx`
- Create: `frontend/src/components/Table.tsx`
- Create: `frontend/src/components/Modal.tsx`
- Create: `frontend/src/components/Tabs.tsx`
- Create: `frontend/src/components/components.css`

**Interfaces:**
- Produces: `<Card>`, `<SeverityBadge severity="P0"|"P1"|"P2">`, `<DimensionDots order={string[]} failed={Set<string>|string[]}>`, `<StatTile label value sublabel?>`, `<Skeleton lines? height?>`, `<Pagination page pageSize total onPageChange>`, `<Table columns rows onRowClick? rowKey>`, `<Modal open onClose title>`, `<Tabs tabs active onChange>`.
- Consumes: `frontend/src/styles/tokens.css` custom properties only — no hardcoded colors.

- [ ] **Step 1: Write the shared component styles**

```css
/* frontend/src/components/components.css */
.card {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-card);
  padding: var(--space-4);
}

.card--clickable {
  cursor: pointer;
  transition: box-shadow 0.15s ease, transform 0.15s ease;
}

.card--clickable:hover {
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.08);
  transform: translateY(-1px);
}

.badge {
  display: inline-block;
  border-radius: 999px;
  padding: 2px 10px;
  font-size: 12px;
  font-weight: 700;
  color: #fff;
}

.badge-p0 { background: var(--severity-p0); }
.badge-p1 { background: var(--severity-p1); }
.badge-p2 { background: var(--severity-p2); }

.dimension-dots {
  font-family: var(--font-family);
  letter-spacing: 2px;
}

.stat-tile {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.stat-tile__value {
  font-size: 28px;
  font-weight: 700;
}

.stat-tile__label {
  color: var(--color-text-secondary);
  font-size: 13px;
}

.skeleton {
  background: linear-gradient(90deg, var(--color-border) 25%, var(--color-panel-tint) 37%, var(--color-border) 63%);
  background-size: 400% 100%;
  animation: skeleton-shimmer 1.4s ease infinite;
  border-radius: 6px;
}

@keyframes skeleton-shimmer {
  0% { background-position: 100% 50%; }
  100% { background-position: 0 50%; }
}

.al-table {
  width: 100%;
  border-collapse: collapse;
}

.al-table th {
  text-align: left;
  font-size: 12px;
  color: var(--color-text-secondary);
  border-bottom: 1px solid var(--color-border);
  padding: var(--space-2);
}

.al-table td {
  padding: var(--space-2);
  border-bottom: 1px solid var(--color-border);
}

.al-table tr[data-clickable="true"]:hover {
  background: var(--color-panel-tint);
  cursor: pointer;
}

.pagination {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: var(--space-2);
}

.tabs {
  display: flex;
  gap: var(--space-4);
  border-bottom: 1px solid var(--color-border);
}

.tabs button {
  background: none;
  border: none;
  padding: var(--space-2) 0;
  font-size: var(--font-size-body);
  color: var(--color-text-secondary);
  cursor: pointer;
  border-bottom: 2px solid transparent;
}

.tabs button[data-active="true"] {
  color: var(--color-text);
  font-weight: 700;
  border-bottom-color: var(--color-primary);
}

.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.4);
  display: flex;
  align-items: center;
  justify-content: center;
}

.modal {
  background: var(--color-surface);
  border-radius: var(--radius-card);
  padding: var(--space-4);
  min-width: 360px;
  max-width: 90vw;
}

.modal__header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--space-3);
}
```

- [ ] **Step 2: Write the components**

```tsx
// frontend/src/components/Card.tsx
import type { ReactNode } from "react";
import "./components.css";

export function Card({
  children,
  clickable = false,
  onClick,
}: {
  children: ReactNode;
  clickable?: boolean;
  onClick?: () => void;
}) {
  return (
    <div className={`card${clickable ? " card--clickable" : ""}`} onClick={onClick}>
      {children}
    </div>
  );
}
```

```tsx
// frontend/src/components/SeverityBadge.tsx
import "./components.css";

const LABELS: Record<string, string> = { P0: "P0", P1: "P1", P2: "P2" };

export function SeverityBadge({ severity }: { severity: string }) {
  const cls = severity === "P0" ? "badge-p0" : severity === "P1" ? "badge-p1" : "badge-p2";
  return <span className={`badge ${cls}`}>{LABELS[severity] ?? severity}</span>;
}
```

```tsx
// frontend/src/components/DimensionDots.tsx
import "./components.css";

export function DimensionDots({
  order,
  failed,
}: {
  order: string[];
  failed: Set<string> | string[];
}) {
  const failedSet = failed instanceof Set ? failed : new Set(failed);
  const dots = order.map((dim) => (failedSet.has(dim) ? "●" : "○")).join("");
  return <span className="dimension-dots">{dots}</span>;
}
```

```tsx
// frontend/src/components/StatTile.tsx
import "./components.css";

export function StatTile({
  label,
  value,
  sublabel,
}: {
  label: string;
  value: string;
  sublabel?: string;
}) {
  return (
    <div className="stat-tile">
      <span className="stat-tile__value numeric">{value}</span>
      <span className="stat-tile__label">{label}</span>
      {sublabel && <span className="stat-tile__label">{sublabel}</span>}
    </div>
  );
}
```

```tsx
// frontend/src/components/Skeleton.tsx
import "./components.css";

export function Skeleton({ lines = 1, height = 16 }: { lines?: number; height?: number }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      {Array.from({ length: lines }).map((_, i) => (
        <div key={i} className="skeleton" style={{ height, width: "100%" }} />
      ))}
    </div>
  );
}
```

```tsx
// frontend/src/components/Pagination.tsx
import "./components.css";

export function Pagination({
  page,
  pageSize,
  total,
  onPageChange,
}: {
  page: number;
  pageSize: number;
  total: number;
  onPageChange: (page: number) => void;
}) {
  const lastPage = Math.max(0, Math.ceil(total / pageSize) - 1);
  return (
    <div className="pagination">
      <button
        className="btn btn-secondary"
        disabled={page === 0}
        onClick={() => onPageChange(page - 1)}
      >
        ← Prev
      </button>
      <span>
        Page {page + 1} of {lastPage + 1}
      </span>
      <button
        className="btn btn-secondary"
        disabled={page >= lastPage}
        onClick={() => onPageChange(page + 1)}
      >
        Next →
      </button>
    </div>
  );
}
```

```tsx
// frontend/src/components/Table.tsx
import "./components.css";

export interface Column<Row> {
  key: string;
  header: string;
  render: (row: Row) => React.ReactNode;
  numeric?: boolean;
}

export function Table<Row>({
  columns,
  rows,
  rowKey,
  onRowClick,
}: {
  columns: Column<Row>[];
  rows: Row[];
  rowKey: (row: Row) => string;
  onRowClick?: (row: Row) => void;
}) {
  return (
    <table className="al-table">
      <thead>
        <tr>
          {columns.map((col) => (
            <th key={col.key}>{col.header}</th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr
            key={rowKey(row)}
            data-clickable={Boolean(onRowClick)}
            onClick={() => onRowClick?.(row)}
          >
            {columns.map((col) => (
              <td key={col.key} className={col.numeric ? "numeric" : undefined}>
                {col.render(row)}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}
```

```tsx
// frontend/src/components/Modal.tsx
import type { ReactNode } from "react";
import "./components.css";

export function Modal({
  open,
  onClose,
  title,
  children,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
}) {
  if (!open) return null;
  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal__header">
          <h3>{title}</h3>
          <button className="btn btn-secondary" onClick={onClose}>
            ✕
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}
```

```tsx
// frontend/src/components/Tabs.tsx
import "./components.css";

export function Tabs({
  tabs,
  active,
  onChange,
}: {
  tabs: string[];
  active: string;
  onChange: (tab: string) => void;
}) {
  return (
    <div className="tabs">
      {tabs.map((tab) => (
        <button key={tab} data-active={tab === active} onClick={() => onChange(tab)}>
          {tab}
        </button>
      ))}
    </div>
  );
}
```

- [ ] **Step 3: Verify the project still type-checks and builds**

Run:
```bash
cd frontend
npm run build
```
Expected: build completes with no TypeScript errors

- [ ] **Step 4: Commit**

```bash
cd /Users/praveendua/Documents/AgenticProjects/agentlens-web
git add frontend/src/components
git commit -m "feat: core design-system components (docs/superpowers/plans/2026-07-13-streamlit-to-web-migration.md)"
```

---

## Task 11: API client, role context, app shell, router

**Files:**
- Create: `frontend/src/api/client.ts`
- Create: `frontend/src/context/RoleContext.tsx`
- Create: `frontend/src/constants.ts`
- Create: `frontend/src/components/AppShell.tsx`
- Create: `frontend/src/router.tsx`
- Modify: `frontend/src/App.tsx`

**Interfaces:**
- Produces: `frontend/src/api/client.ts` exporting typed fetch functions (`fetchStatus`, `fetchOverview`, `fetchConversations`, `fetchConversationDetail`, `fetchClusters`, `fetchReviewQueue`, `submitReview`, `fetchFixWorkbenchClusters`, `fetchFixWorkbench`, `generateFix`, `applyRegression`, `fetchJobsStatus`, `fetchEvalEstimate`, `launchCorpusJob`, `launchEvalsJob`, `launchReclusterJob`) and the matching TS interfaces (`StatusSummary`, `ConversationRow`, `ClusterCard`, `Overview`, `CallDetail`, `ReviewQueueState`, `Finding`, `FixWorkbenchState`, `FixProposal`, `RegressionRun`, `JobsStatus`) — every later route file imports from here, never calling `fetch` directly. `useRole()` hook from `RoleContext.tsx`. `PAGES_BY_ROLE` and `NAV_ROUTES` from `constants.ts`.
- Consumes: FastAPI endpoints from Tasks 3–8; components from Task 10.

- [ ] **Step 1: Write the typed API client**

```typescript
// frontend/src/api/client.ts
const BASE = "/api";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!response.ok) {
    const body = await response.text();
    throw new Error(`${init?.method ?? "GET"} ${path} failed (${response.status}): ${body}`);
  }
  return response.json() as Promise<T>;
}

export interface StatusSummary {
  last_eval_at: string | null;
  n_calls: number;
  n_golden: number;
}

export interface ConversationRow {
  call_id: string;
  scenario: string;
  failed_dimensions: string[];
  has_p0: boolean;
  avg_score: number;
  est_cost_cents: number;
  created_at: string;
}

export interface ClusterLabel {
  id: number;
  label: string;
}

export interface ConversationsList {
  rows: ConversationRow[];
  total: number;
  clusters: ClusterLabel[];
}

export interface EvalRecordDetail {
  id: number;
  dimension: string;
  score: number;
  severity: string;
  passed: boolean;
  failure_description: string | null;
  judge_reasoning: string;
  pipeline_stage: string | null;
  judge_model: string;
  prompt_version: string;
  rubric_version: string;
  input_hash: string;
}

export interface CheckResult {
  check_name: string;
  triggered: boolean;
  detail: string | null;
}

export interface CallDetail {
  call_id: string;
  scenario: string;
  transcript: { speaker?: string; text?: string }[];
  records: EvalRecordDetail[];
  checks: CheckResult[];
  cluster: { id: number; label: string } | null;
  ground_truth: { failure_mode: string; pipeline_stage: string; severity: string } | null;
}

export interface ClusterCard {
  cluster_id: number;
  label: string;
  description: string;
  routing: string;
  severity: string;
  size: number;
  is_p0: boolean;
}

export interface ClustersList {
  cards: ClusterCard[];
  n_failures: number;
  last_clustered_at: string | null;
}

export interface DimensionQuality {
  pass_rate: number;
  delta: number | null;
}

export interface Overview {
  quality: Record<string, DimensionQuality>;
  severities: Record<string, number>;
  precision: number | null;
  recall: number | null;
  agreement: number | null;
  n_reviews: number;
  top_clusters: ClusterCard[];
  total_eval_cents: number;
  avg_per_call_cents: number;
}

export interface AgreementStats {
  n_reviews: number;
  n_agree: number;
  agreement: number;
  per_dimension: Record<string, number>;
  per_dimension_counts: Record<string, number>;
}

export interface Finding {
  eval_record_id: number;
  call_id: string;
  scenario: string;
  dimension: string;
  score: number;
  severity: string;
  failure_description: string | null;
  checks: CheckResult[];
  transcript: { speaker?: string; text?: string }[];
}

export interface ReviewQueueState {
  stats: AgreementStats;
  pending_count: number;
  current: Finding | null;
}

export interface FixProposal {
  id: number;
  cluster_id: number;
  fix_type: string;
  rationale: string;
  patch: string;
  status: string;
}

export interface RegressionRun {
  id: number;
  fix_proposal_id: number;
  batch_id: string;
  n_before: number;
  n_after: number;
  before_pass_rates: Record<string, number>;
  after_pass_rates: Record<string, number>;
  target_dimension: string;
  regressed_dimensions: string[];
}

export interface FixWorkbenchState {
  cluster: ClusterCard;
  fix: FixProposal | null;
  regression: RegressionRun | null;
}

export interface JobSummary {
  finished_at: string | null;
  summary: Record<string, unknown>;
}

export interface JobsStatus {
  corpus: JobSummary;
  evals: JobSummary;
  cluster: JobSummary;
  log_lines: string[];
}

export const fetchStatus = () => request<StatusSummary>("/status");

export const fetchOverview = () => request<Overview>("/overview");

export function fetchConversations(params: {
  severity?: string;
  dimension?: string;
  clusterId?: number;
  outcome?: "pass" | "fail";
  page?: number;
}): Promise<ConversationsList> {
  const q = new URLSearchParams();
  if (params.severity) q.set("severity", params.severity);
  if (params.dimension) q.set("dimension", params.dimension);
  if (params.clusterId != null) q.set("cluster_id", String(params.clusterId));
  if (params.outcome) q.set("outcome", params.outcome);
  q.set("page", String(params.page ?? 0));
  return request<ConversationsList>(`/conversations?${q.toString()}`);
}

export const fetchConversationDetail = (callId: string) =>
  request<CallDetail>(`/conversations/${encodeURIComponent(callId)}`);

export function fetchClusters(params: {
  routing?: string;
  severity?: string;
  focusId?: number;
}): Promise<ClustersList> {
  const q = new URLSearchParams();
  if (params.routing) q.set("routing", params.routing);
  if (params.severity) q.set("severity", params.severity);
  if (params.focusId != null) q.set("focus_id", String(params.focusId));
  return request<ClustersList>(`/clusters?${q.toString()}`);
}

export const fetchReviewQueue = () => request<ReviewQueueState>("/review-queue");

export const submitReview = (evalRecordId: number, verdict: "agree" | "disagree", note?: string) =>
  request<ReviewQueueState>(`/review-queue/${evalRecordId}`, {
    method: "POST",
    body: JSON.stringify({ verdict, note: note ?? null }),
  });

export const fetchFixWorkbenchClusters = () => request<ClusterLabel[]>("/fix-workbench/clusters");

export const fetchFixWorkbench = (clusterId: number) =>
  request<FixWorkbenchState>(`/fix-workbench/${clusterId}`);

export const generateFix = (clusterId: number) =>
  request<FixProposal>(`/fix-workbench/${clusterId}/generate`, { method: "POST" });

export const applyRegression = (clusterId: number) =>
  request<RegressionRun>(`/fix-workbench/${clusterId}/apply-regression`, { method: "POST" });

export const fetchJobsStatus = () => request<JobsStatus>("/jobs/status");

export const fetchEvalEstimate = (scope: string, model: string) =>
  request<{ n_calls: number; estimate_cents: number }>(
    `/jobs/eval-estimate?scope=${scope}&model=${model}`
  );

export const launchCorpusJob = (count: number, failureRate: number) =>
  request<{ status: string }>("/jobs/corpus", {
    method: "POST",
    body: JSON.stringify({ count, failure_rate: failureRate }),
  });

export const launchEvalsJob = (scope: string, model: string) =>
  request<{ status: string }>("/jobs/evals", {
    method: "POST",
    body: JSON.stringify({ scope, model }),
  });

export const launchReclusterJob = () =>
  request<{ status: string }>("/jobs/recluster", { method: "POST" });
```

- [ ] **Step 2: Write the role context**

```tsx
// frontend/src/context/RoleContext.tsx
import { createContext, useContext, useState, type ReactNode } from "react";

export type Role = "Engineer" | "Reviewer" | "Lead";

const ROLE_KEY = "agentlens.role";

interface RoleContextValue {
  role: Role;
  setRole: (role: Role) => void;
}

const RoleContext = createContext<RoleContextValue | null>(null);

export function RoleProvider({ children }: { children: ReactNode }) {
  const [role, setRoleState] = useState<Role>(() => {
    const stored = sessionStorage.getItem(ROLE_KEY);
    return stored === "Engineer" || stored === "Reviewer" || stored === "Lead"
      ? stored
      : "Engineer";
  });

  const setRole = (next: Role) => {
    sessionStorage.setItem(ROLE_KEY, next);
    setRoleState(next);
  };

  return <RoleContext.Provider value={{ role, setRole }}>{children}</RoleContext.Provider>;
}

export function useRole(): RoleContextValue {
  const ctx = useContext(RoleContext);
  if (!ctx) throw new Error("useRole must be used within a RoleProvider");
  return ctx;
}
```

- [ ] **Step 3: Write the nav constants**

```typescript
// frontend/src/constants.ts
import type { Role } from "./context/RoleContext";

export const PAGES_BY_ROLE: Record<Role, string[]> = {
  Engineer: ["Overview", "Conversations", "Clusters", "Fix Workbench", "Jobs"],
  Reviewer: ["Overview", "Review Queue"],
  Lead: ["Overview", "Conversations", "Clusters"],
};

export const NAV_ROUTES: Record<string, string> = {
  Overview: "/",
  Conversations: "/conversations",
  Clusters: "/clusters",
  "Review Queue": "/review-queue",
  "Fix Workbench": "/fix-workbench",
  Jobs: "/jobs",
};

export const DIMENSION_ORDER = [
  "task_completion",
  "factual_accuracy",
  "safety_compliance",
  "communication_quality",
];
```

- [ ] **Step 4: Write the app shell**

```tsx
// frontend/src/components/AppShell.tsx
import { NavLink, Outlet } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { useRole } from "../context/RoleContext";
import { PAGES_BY_ROLE, NAV_ROUTES } from "../constants";
import { fetchStatus } from "../api/client";
import "./app-shell.css";

export function AppShell() {
  const { role, setRole } = useRole();
  const { data: status } = useQuery({ queryKey: ["status"], queryFn: fetchStatus });

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <h1 className="sidebar__title">AgentLens</h1>
        <select
          className="select"
          value={role}
          onChange={(e) => setRole(e.target.value as typeof role)}
        >
          <option value="Engineer">Engineer</option>
          <option value="Reviewer">Reviewer</option>
          <option value="Lead">Lead</option>
        </select>
        <hr />
        <nav>
          {PAGES_BY_ROLE[role].map((title) => (
            <NavLink
              key={title}
              to={NAV_ROUTES[title]}
              end={NAV_ROUTES[title] === "/"}
              className={({ isActive }) => `nav-link${isActive ? " nav-link--active" : ""}`}
            >
              {title}
            </NavLink>
          ))}
        </nav>
        <hr />
        {status && (
          <p className="sidebar__status text-dense">
            Last eval run: {status.last_eval_at ? new Date(status.last_eval_at).toLocaleString() : "never"}
            <br />
            Corpus calls: {status.n_calls}
            <br />
            Golden calls: {status.n_golden}
          </p>
        )}
      </aside>
      <main className="content">
        <Outlet />
      </main>
    </div>
  );
}
```

```css
/* frontend/src/components/app-shell.css */
.app-shell {
  display: grid;
  grid-template-columns: 240px 1fr;
  min-height: 100vh;
}

.sidebar {
  background: var(--color-surface);
  border-right: 1px solid var(--color-border);
  padding: var(--space-4);
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.sidebar__title {
  background: var(--color-accent-gradient);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
  font-size: 22px;
}

.nav-link {
  display: block;
  padding: var(--space-2);
  color: var(--color-text);
  text-decoration: none;
  border-left: 3px solid transparent;
}

.nav-link--active {
  border-left-color: var(--color-primary);
  font-weight: 700;
}

.sidebar__status {
  color: var(--color-text-secondary);
}

.content {
  padding: var(--space-5);
}
```

- [ ] **Step 5: Write the router and app entry**

```tsx
// frontend/src/router.tsx
import { createBrowserRouter } from "react-router-dom";
import { AppShell } from "./components/AppShell";
import { Overview } from "./routes/Overview";
import { Conversations } from "./routes/Conversations";
import { CallDetail } from "./routes/CallDetail";
import { Clusters } from "./routes/Clusters";
import { ReviewQueue } from "./routes/ReviewQueue";
import { FixWorkbench } from "./routes/FixWorkbench";
import { Jobs } from "./routes/Jobs";

export const router = createBrowserRouter([
  {
    element: <AppShell />,
    children: [
      { path: "/", element: <Overview /> },
      { path: "/conversations", element: <Conversations /> },
      { path: "/calls/:callId", element: <CallDetail /> },
      { path: "/clusters", element: <Clusters /> },
      { path: "/review-queue", element: <ReviewQueue /> },
      { path: "/fix-workbench", element: <FixWorkbench /> },
      { path: "/jobs", element: <Jobs /> },
    ],
  },
]);
```

```tsx
// frontend/src/App.tsx
import { RouterProvider } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RoleProvider } from "./context/RoleContext";
import { router } from "./router";

const queryClient = new QueryClient();

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <RoleProvider>
        <RouterProvider router={router} />
      </RoleProvider>
    </QueryClientProvider>
  );
}
```

Note: this task's build will not type-check until the seven route files exist (Tasks 12–17 create them). Create minimal placeholder route files now so Task 11 builds independently:

```tsx
// frontend/src/routes/Overview.tsx (placeholder, replaced in Task 12)
export function Overview() {
  return <div>Overview</div>;
}
```

Create the same one-line placeholder pattern for `Conversations.tsx`, `CallDetail.tsx`, `Clusters.tsx`, `ReviewQueue.tsx`, `FixWorkbench.tsx`, and `Jobs.tsx`, each exporting a correspondingly named function component.

- [ ] **Step 6: Verify the app builds and the dev server serves the shell**

```bash
cd frontend
npm run build
```
Expected: build completes with no TypeScript errors.

```bash
uv run uvicorn agentlens.api.main:app --reload --port 8000 &
cd frontend && npm run dev &
```
Open `http://localhost:5173` — expect the AgentLens sidebar with a role selector and nav links, "Overview" placeholder text in the content area, and the status block populated (or "never"/0s on an empty DB) confirming the `/api/status` fetch through the Vite proxy succeeded. Stop both background processes afterward (`kill %1 %2` or close the terminals).

- [ ] **Step 7: Commit**

```bash
cd /Users/praveendua/Documents/AgenticProjects/agentlens-web
git add frontend/src
git commit -m "feat: API client, role context, app shell, router (docs/superpowers/plans/2026-07-13-streamlit-to-web-migration.md)"
```

---

## Task 12: Overview page

**Files:**
- Modify: `frontend/src/routes/Overview.tsx`

**Interfaces:**
- Consumes: `fetchOverview` from `api/client.ts`; `Card`, `StatTile`, `Skeleton` from `components/`; `NAV_ROUTES`, `DIMENSION_ORDER` from `constants.ts`; `useNavigate` from `react-router-dom`.

- [ ] **Step 1: Implement the page**

```tsx
// frontend/src/routes/Overview.tsx
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { fetchOverview } from "../api/client";
import { Card } from "../components/Card";
import { Skeleton } from "../components/Skeleton";
import { StatTile } from "../components/StatTile";

export function Overview() {
  const navigate = useNavigate();
  const { data, isLoading } = useQuery({ queryKey: ["overview"], queryFn: fetchOverview });

  if (isLoading || !data) {
    return (
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 24 }}>
        {Array.from({ length: 4 }).map((_, i) => (
          <Card key={i}>
            <Skeleton lines={4} />
          </Card>
        ))}
      </div>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
      <h2>Overview</h2>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 24 }}>
        <Card>
          <h3>Quality</h3>
          {Object.entries(data.quality).map(([dim, q]) => {
            const arrow =
              q.delta == null ? "" : q.delta >= 0 ? ` ▲ ${Math.round(q.delta * 100)}%` : ` ▼ ${Math.round(q.delta * 100)}%`;
            return (
              <div key={dim} style={{ marginBottom: 8 }}>
                <div className="text-dense">
                  {dim}: {Math.round(q.pass_rate * 100)}%{arrow}
                </div>
                <progress value={q.pass_rate} max={1} style={{ width: "100%" }} />
              </div>
            );
          })}
        </Card>

        <Card>
          <h3>Severity</h3>
          {Object.entries(data.severities).map(([sev, count]) => (
            <button
              key={sev}
              className="btn btn-secondary"
              style={{ display: "block", marginBottom: 8, width: "100%", textAlign: "left" }}
              onClick={() => navigate(`/conversations?severity=${sev}`)}
            >
              {sev}: {count} findings
            </button>
          ))}
        </Card>

        <Card>
          <h3>Judge Accuracy</h3>
          <StatTile label="Precision (golden)" value={data.precision != null ? data.precision.toFixed(2) : "—"} />
          <StatTile label="Recall (golden)" value={data.recall != null ? data.recall.toFixed(2) : "—"} />
          <StatTile
            label="Human agreement"
            value={data.agreement != null ? `${Math.round(data.agreement * 100)}% (${data.n_reviews})` : "—"}
          />
        </Card>

        <Card>
          <h3>Top Clusters</h3>
          {data.top_clusters.length === 0 && (
            <p className="text-dense">No clusters yet — run clustering from the Jobs page.</p>
          )}
          {data.top_clusters.map((c) => (
            <button
              key={c.cluster_id}
              className="btn btn-secondary"
              style={{ display: "block", marginBottom: 8, width: "100%", textAlign: "left" }}
              onClick={() => navigate(`/clusters?focus_id=${c.cluster_id}`)}
            >
              {c.label} · {c.size} · {c.severity} · {c.routing}
            </button>
          ))}
        </Card>
      </div>

      <Card>
        <p className="text-dense">
          Total eval cost to date: {(data.total_eval_cents / 100).toFixed(2)} USD · avg{" "}
          {data.avg_per_call_cents.toFixed(2)}¢ per call
        </p>
      </Card>
    </div>
  );
}
```

- [ ] **Step 2: Verify the build and manually check the page**

```bash
cd frontend && npm run build
```
Expected: no TypeScript errors.

With both servers running (per Task 11 Step 6), open `http://localhost:5173/` and confirm the four cards render (empty-state text on an empty DB is fine), and clicking a severity button navigates to `/conversations?severity=P0` (a blank Conversations placeholder page is expected until Task 13).

- [ ] **Step 3: Commit**

```bash
git add frontend/src/routes/Overview.tsx
git commit -m "feat: Overview page (docs/superpowers/plans/2026-07-13-streamlit-to-web-migration.md)"
```

---

## Task 13: Conversations + Call Detail pages

**Files:**
- Modify: `frontend/src/routes/Conversations.tsx`
- Modify: `frontend/src/routes/CallDetail.tsx`

**Interfaces:**
- Consumes: `fetchConversations`, `fetchConversationDetail` from `api/client.ts`; `Table`, `Pagination`, `DimensionDots`, `SeverityBadge`, `Card`, `Skeleton` from `components/`; `useSearchParams`, `useNavigate`, `useParams` from `react-router-dom`.

- [ ] **Step 1: Implement the Conversations list page**

```tsx
// frontend/src/routes/Conversations.tsx
import { useQuery } from "@tanstack/react-query";
import { useNavigate, useSearchParams } from "react-router-dom";
import { fetchConversations } from "../api/client";
import type { ConversationRow } from "../api/client";
import { Table, type Column } from "../components/Table";
import { Pagination } from "../components/Pagination";
import { DimensionDots } from "../components/DimensionDots";
import { Skeleton } from "../components/Skeleton";
import { DIMENSION_ORDER } from "../constants";

const PAGE_SIZE = 25;

export function Conversations() {
  const [params, setParams] = useSearchParams();
  const navigate = useNavigate();

  const severity = params.get("severity") ?? undefined;
  const dimension = params.get("dimension") ?? undefined;
  const clusterId = params.get("cluster_id") ? Number(params.get("cluster_id")) : undefined;
  const outcome = (params.get("outcome") as "pass" | "fail" | null) ?? undefined;
  const page = Number(params.get("page") ?? "0");

  const { data, isLoading } = useQuery({
    queryKey: ["conversations", severity, dimension, clusterId, outcome, page],
    queryFn: () => fetchConversations({ severity, dimension, clusterId, outcome, page }),
  });

  const setFilter = (key: string, value: string) => {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value);
    else next.delete(key);
    next.set("page", "0");
    setParams(next);
  };

  const columns: Column<ConversationRow>[] = [
    { key: "id", header: "ID", render: (r) => r.call_id },
    { key: "scenario", header: "Scenario", render: (r) => r.scenario },
    {
      key: "fails",
      header: "Fails",
      render: (r) => <DimensionDots order={DIMENSION_ORDER} failed={r.failed_dimensions} />,
    },
    { key: "p0", header: "P0", render: (r) => (r.has_p0 ? "⚠" : "") },
    { key: "score", header: "Avg Score", render: (r) => r.avg_score.toFixed(1), numeric: true },
    { key: "cost", header: "Cost (est ¢)", render: (r) => r.est_cost_cents.toFixed(2), numeric: true },
    { key: "date", header: "Date", render: (r) => new Date(r.created_at).toLocaleString() },
  ];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <h2>Conversations</h2>
      <div style={{ display: "flex", gap: 16 }}>
        <select className="select" value={severity ?? ""} onChange={(e) => setFilter("severity", e.target.value)}>
          <option value="">All severities</option>
          <option value="P0">P0</option>
          <option value="P1">P1</option>
          <option value="P2">P2</option>
        </select>
        <select className="select" value={dimension ?? ""} onChange={(e) => setFilter("dimension", e.target.value)}>
          <option value="">All dimensions</option>
          {DIMENSION_ORDER.map((d) => (
            <option key={d} value={d}>
              {d}
            </option>
          ))}
        </select>
        <select
          className="select"
          value={clusterId ?? ""}
          onChange={(e) => setFilter("cluster_id", e.target.value)}
        >
          <option value="">All clusters</option>
          {data?.clusters.map((c) => (
            <option key={c.id} value={c.id}>
              {c.label}
            </option>
          ))}
        </select>
        <select className="select" value={outcome ?? ""} onChange={(e) => setFilter("outcome", e.target.value)}>
          <option value="">All outcomes</option>
          <option value="pass">Pass only</option>
          <option value="fail">Fail only</option>
        </select>
      </div>

      {isLoading || !data ? (
        <Skeleton lines={8} height={32} />
      ) : (
        <>
          <p className="text-dense">
            {data.total} calls · {data.rows.filter((r) => r.failed_dimensions.length).length} with failures ·{" "}
            {data.rows.filter((r) => r.has_p0).length} P0
          </p>
          <Table
            columns={columns}
            rows={data.rows}
            rowKey={(r) => r.call_id}
            onRowClick={(r) => navigate(`/calls/${r.call_id}?from=conversations`)}
          />
          <Pagination
            page={page}
            pageSize={PAGE_SIZE}
            total={data.total}
            onPageChange={(next) => {
              const p = new URLSearchParams(params);
              p.set("page", String(next));
              setParams(p);
            }}
          />
        </>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Implement the Call Detail page**

```tsx
// frontend/src/routes/CallDetail.tsx
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { fetchConversationDetail } from "../api/client";
import { Card } from "../components/Card";
import { Skeleton } from "../components/Skeleton";
import { SeverityBadge } from "../components/SeverityBadge";
import { useRole } from "../context/RoleContext";

export function CallDetail() {
  const { callId } = useParams<{ callId: string }>();
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const { role } = useRole();
  const [showGroundTruth, setShowGroundTruth] = useState(false);

  const { data, isLoading } = useQuery({
    queryKey: ["call", callId],
    queryFn: () => fetchConversationDetail(callId!),
    enabled: Boolean(callId),
  });

  if (isLoading || !data) {
    return (
      <Card>
        <Skeleton lines={10} />
      </Card>
    );
  }

  const origin = params.get("from") === "review-queue" ? "/review-queue" : "/conversations";

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <div style={{ display: "flex", justifyContent: "space-between" }}>
        <button className="btn btn-secondary" onClick={() => navigate(origin)}>
          ← Back
        </button>
        {data.cluster && (
          <button className="btn btn-secondary" onClick={() => navigate(`/clusters?focus_id=${data.cluster!.id}`)}>
            View cluster → {data.cluster.label}
          </button>
        )}
      </div>

      <h2>
        Call {data.call_id} · {data.scenario}
      </h2>

      <Card>
        <h3>Transcript</h3>
        <div style={{ maxHeight: 300, overflowY: "auto" }} className="text-dense">
          {data.transcript.map((turn, i) => (
            <p key={i}>
              <strong>{(turn.speaker ?? "").toString().replace(/^\w/, (c) => c.toUpperCase())}:</strong>{" "}
              {turn.text}
            </p>
          ))}
        </div>
      </Card>

      <h3>Scores</h3>
      {data.records.map((record) => (
        <details key={record.id} style={{ marginBottom: 8 }}>
          <summary>
            {record.dimension} · {record.score} · <SeverityBadge severity={record.severity} /> ·{" "}
            {record.passed ? "pass" : "FAIL"} · stage: {record.pipeline_stage ?? "—"}
          </summary>
          <div className="text-dense" style={{ padding: 12 }}>
            <p>{record.judge_reasoning}</p>
            {record.failure_description && <p><strong>Finding:</strong> {record.failure_description}</p>}
            <p><strong>Deterministic checks:</strong></p>
            <p>
              {data.checks.length
                ? data.checks.map((c) => (c.triggered ? `⚠ ${c.check_name.toUpperCase()}` : `✓ ${c.check_name}`)).join(" · ")
                : "✓ No deterministic flags"}
            </p>
            <p style={{ color: "var(--color-text-secondary)" }}>
              Prompt v{record.prompt_version} · Model: {record.judge_model} · Rubric v{record.rubric_version} ·
              Input hash: {record.input_hash}
            </p>
          </div>
        </details>
      ))}

      {role === "Engineer" && (
        <label className="text-dense">
          <input type="checkbox" checked={showGroundTruth} onChange={(e) => setShowGroundTruth(e.target.checked)} />{" "}
          Show ground truth
        </label>
      )}
      {showGroundTruth && role === "Engineer" && (
        <Card>
          {data.ground_truth ? (
            <p>
              Injected: {data.ground_truth.failure_mode} · stage: {data.ground_truth.pipeline_stage} · severity:{" "}
              {data.ground_truth.severity}
            </p>
          ) : (
            <p>No injected failure — this is a clean call.</p>
          )}
        </Card>
      )}
    </div>
  );
}
```

- [ ] **Step 3: Verify the build and manually check both pages**

```bash
cd frontend && npm run build
```
Expected: no TypeScript errors.

With both servers running, open `http://localhost:5173/conversations`. On an empty DB the table is empty but filters/pagination render without error; if you have seeded data (e.g. from `uv run pytest tests/api/test_conversations.py` fixtures, or by running the real corpus/eval jobs), confirm a row click navigates to `/calls/<id>` and renders the transcript, score expanders, and (for Engineer role) the ground-truth toggle.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/routes/Conversations.tsx frontend/src/routes/CallDetail.tsx
git commit -m "feat: Conversations and Call Detail pages (docs/superpowers/plans/2026-07-13-streamlit-to-web-migration.md)"
```

---

## Task 14: Clusters page

**Files:**
- Modify: `frontend/src/routes/Clusters.tsx`

**Interfaces:**
- Consumes: `fetchClusters` from `api/client.ts`; `Card`, `SeverityBadge`, `Skeleton` from `components/`; `useSearchParams`, `useNavigate`.

- [ ] **Step 1: Implement the page**

```tsx
// frontend/src/routes/Clusters.tsx
import { useQuery } from "@tanstack/react-query";
import { useNavigate, useSearchParams } from "react-router-dom";
import { fetchClusters } from "../api/client";
import { Card } from "../components/Card";
import { SeverityBadge } from "../components/SeverityBadge";
import { Skeleton } from "../components/Skeleton";

export function Clusters() {
  const [params, setParams] = useSearchParams();
  const navigate = useNavigate();

  const routing = params.get("routing") ?? undefined;
  const severity = params.get("severity") ?? undefined;
  const focusId = params.get("focus_id") ? Number(params.get("focus_id")) : undefined;

  const { data, isLoading } = useQuery({
    queryKey: ["clusters", routing, severity, focusId],
    queryFn: () => fetchClusters({ routing, severity, focusId }),
  });

  const setFilter = (key: string, value: string) => {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value);
    else next.delete(key);
    setParams(next);
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <h2>Clusters</h2>
      {focusId != null && (
        <button
          className="btn btn-secondary"
          style={{ alignSelf: "flex-start" }}
          onClick={() => {
            const next = new URLSearchParams(params);
            next.delete("focus_id");
            setParams(next);
          }}
        >
          Show all clusters
        </button>
      )}
      <div style={{ display: "flex", gap: 16 }}>
        <select className="select" value={routing ?? ""} onChange={(e) => setFilter("routing", e.target.value)}>
          <option value="">All routing</option>
          <option value="prompt_fix">prompt_fix</option>
          <option value="retrieval_data_fix">retrieval_data_fix</option>
          <option value="ops_process">ops_process</option>
          <option value="model_config">model_config</option>
        </select>
        <select className="select" value={severity ?? ""} onChange={(e) => setFilter("severity", e.target.value)}>
          <option value="">All severities</option>
          <option value="P0">P0</option>
          <option value="P1">P1</option>
          <option value="P2">P2</option>
        </select>
      </div>

      {isLoading || !data ? (
        <Skeleton lines={6} height={80} />
      ) : (
        <>
          <p className="text-dense">
            {data.cards.length} clusters · {data.n_failures} failures · last clustered{" "}
            {data.last_clustered_at ? new Date(data.last_clustered_at).toLocaleTimeString() : "never"}
          </p>
          {data.cards.map((card) => (
            <Card key={card.cluster_id}>
              <h3>
                <SeverityBadge severity={card.severity} /> {card.label} · {card.size} calls
              </h3>
              <p className="text-dense" style={{ color: "var(--color-text-secondary)" }}>
                routing: {card.routing} · dominant severity: {card.severity}
              </p>
              <p className="text-dense">{card.description}</p>
              <div style={{ display: "flex", gap: 8 }}>
                <button
                  className="btn btn-secondary"
                  onClick={() => navigate(`/conversations?cluster_id=${card.cluster_id}`)}
                >
                  View {card.size} calls
                </button>
                <button
                  className="btn btn-primary"
                  disabled={card.is_p0}
                  title={card.is_p0 ? "P0 findings require human resolution before a fix can be proposed" : undefined}
                  onClick={() => navigate(`/fix-workbench?cluster_id=${card.cluster_id}`)}
                >
                  Propose Fix
                </button>
              </div>
            </Card>
          ))}
        </>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Verify the build**

```bash
cd frontend && npm run build
```
Expected: no TypeScript errors. Manually confirm at `http://localhost:5173/clusters` that filters update the URL and (with seeded data) that "View N calls" and "Propose Fix" navigate correctly, and "Propose Fix" is disabled with a tooltip on P0 cards.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/routes/Clusters.tsx
git commit -m "feat: Clusters page (docs/superpowers/plans/2026-07-13-streamlit-to-web-migration.md)"
```

---

## Task 15: Review Queue page

**Files:**
- Modify: `frontend/src/routes/ReviewQueue.tsx`

**Interfaces:**
- Consumes: `fetchReviewQueue`, `submitReview` from `api/client.ts`; `Card`, `StatTile`, `Skeleton` from `components/`; `useNavigate`; `useMutation`/`useQuery`/`useQueryClient` from `@tanstack/react-query`.

- [ ] **Step 1: Implement the page**

```tsx
// frontend/src/routes/ReviewQueue.tsx
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { fetchReviewQueue, submitReview } from "../api/client";
import { Card } from "../components/Card";
import { StatTile } from "../components/StatTile";
import { Skeleton } from "../components/Skeleton";

export function ReviewQueue() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [verdict, setVerdict] = useState<"agree" | "disagree" | null>(null);
  const [note, setNote] = useState("");
  const [showTranscript, setShowTranscript] = useState(false);

  const { data, isLoading } = useQuery({ queryKey: ["review-queue"], queryFn: fetchReviewQueue });

  const mutation = useMutation({
    mutationFn: (vars: { id: number; verdict: "agree" | "disagree"; note?: string }) =>
      submitReview(vars.id, vars.verdict, vars.note),
    onSuccess: (result) => {
      queryClient.setQueryData(["review-queue"], result);
      setVerdict(null);
      setNote("");
      setShowTranscript(false);
    },
  });

  if (isLoading || !data) {
    return (
      <Card>
        <Skeleton lines={6} />
      </Card>
    );
  }

  const { stats, current } = data;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <h2>Review Queue</h2>
      <Card>
        <div style={{ display: "flex", gap: 32 }}>
          <StatTile label="Agreement" value={stats.n_reviews ? `${Math.round(stats.agreement * 100)}%` : "—"} />
          <StatTile label="Reviews" value={String(stats.n_reviews)} />
          <StatTile label="Pending" value={String(data.pending_count)} />
        </div>
        {Object.keys(stats.per_dimension).length > 0 && (
          <p className="text-dense">
            {Object.entries(stats.per_dimension)
              .sort(([a], [b]) => a.localeCompare(b))
              .map(([dim, rate]) => `${dim}: ${Math.round(rate * 100)}% (${stats.per_dimension_counts[dim]})`)
              .join(" · ")}
          </p>
        )}
      </Card>

      {!current ? (
        <Card>
          <p>Queue clear — every flagged finding has a verdict.</p>
        </Card>
      ) : (
        <>
          <Card>
            <h3>
              {current.call_id} · {current.scenario}
            </h3>
            <p>
              <strong>{current.dimension}</strong> · score {current.score} · {current.severity}
            </p>
            <p className="text-dense">{current.failure_description ?? "(no description)"}</p>
            <p className="text-dense">
              {current.checks.length
                ? current.checks
                    .map((c) => (c.triggered ? `⚠ ${c.check_name.toUpperCase()}` : `✓ ${c.check_name}`))
                    .join(" · ")
                : "✓ No deterministic flags"}
            </p>
            <button className="btn btn-secondary" onClick={() => setShowTranscript((v) => !v)}>
              {showTranscript ? "Hide" : "View"} full transcript
            </button>
            {showTranscript && (
              <div className="text-dense" style={{ marginTop: 8 }}>
                {current.transcript.map((turn, i) => (
                  <p key={i}>
                    <strong>{(turn.speaker ?? "").toString().replace(/^\w/, (c) => c.toUpperCase())}:</strong>{" "}
                    {turn.text}
                  </p>
                ))}
              </div>
            )}
          </Card>

          <Card>
            <div style={{ display: "flex", gap: 8, marginBottom: 8 }}>
              <button
                className={verdict === "agree" ? "btn btn-primary" : "btn btn-secondary"}
                onClick={() => setVerdict("agree")}
              >
                ✓ Agree
              </button>
              <button
                className={verdict === "disagree" ? "btn btn-primary" : "btn btn-secondary"}
                onClick={() => setVerdict("disagree")}
              >
                ✗ Disagree
              </button>
            </div>
            <textarea
              className="text-dense"
              placeholder="Note (optional)"
              value={note}
              onChange={(e) => setNote(e.target.value)}
              style={{ width: "100%", minHeight: 60 }}
            />
            <button
              className="btn btn-primary"
              disabled={verdict === null || mutation.isPending}
              onClick={() => verdict && mutation.mutate({ id: current.eval_record_id, verdict, note: note || undefined })}
              style={{ marginTop: 8 }}
            >
              Submit & Next
            </button>
          </Card>
        </>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Verify the build and manually check the flow**

```bash
cd frontend && npm run build
```
Expected: no TypeScript errors. With seeded review-queue data, confirm selecting a verdict enables "Submit & Next", submitting advances to the next finding or shows "Queue clear", and stats update in place without a full page reload.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/routes/ReviewQueue.tsx
git commit -m "feat: Review Queue page (docs/superpowers/plans/2026-07-13-streamlit-to-web-migration.md)"
```

---

## Task 16: Fix Workbench page

**Files:**
- Modify: `frontend/src/routes/FixWorkbench.tsx`

**Interfaces:**
- Consumes: `fetchFixWorkbenchClusters`, `fetchFixWorkbench`, `generateFix`, `applyRegression` from `api/client.ts`; `Card` from `components/`; `useSearchParams`; `useMutation`/`useQuery`/`useQueryClient`.

- [ ] **Step 1: Implement the page**

```tsx
// frontend/src/routes/FixWorkbench.tsx
import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import {
  applyRegression,
  fetchFixWorkbench,
  fetchFixWorkbenchClusters,
  generateFix,
} from "../api/client";
import { Card } from "../components/Card";
import { Skeleton } from "../components/Skeleton";

export function FixWorkbench() {
  const [params] = useSearchParams();
  const queryClient = useQueryClient();
  const presetId = params.get("cluster_id") ? Number(params.get("cluster_id")) : null;
  const [clusterId, setClusterId] = useState<number | null>(presetId);
  const [error, setError] = useState<string | null>(null);

  const { data: selectable } = useQuery({
    queryKey: ["fix-workbench-clusters"],
    queryFn: fetchFixWorkbenchClusters,
  });

  useEffect(() => {
    if (clusterId == null && selectable && selectable.length > 0) {
      setClusterId(selectable[0].id);
    }
  }, [selectable, clusterId]);

  const { data: workbench, isLoading } = useQuery({
    queryKey: ["fix-workbench", clusterId],
    queryFn: () => fetchFixWorkbench(clusterId!),
    enabled: clusterId != null,
  });

  const generateMutation = useMutation({
    mutationFn: () => generateFix(clusterId!),
    onSuccess: () => {
      setError(null);
      queryClient.invalidateQueries({ queryKey: ["fix-workbench", clusterId] });
    },
    onError: (e: Error) => setError(e.message),
  });

  const regressionMutation = useMutation({
    mutationFn: () => applyRegression(clusterId!),
    onSuccess: () => {
      setError(null);
      queryClient.invalidateQueries({ queryKey: ["fix-workbench", clusterId] });
    },
    onError: (e: Error) => setError(e.message),
  });

  if (!selectable || selectable.length === 0) {
    return (
      <Card>
        <p>No non-P0 clusters available — run clustering from the Jobs page.</p>
      </Card>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <h2>Fix Workbench</h2>
      <select
        className="select"
        value={clusterId ?? ""}
        onChange={(e) => setClusterId(Number(e.target.value))}
      >
        {selectable.map((c) => (
          <option key={c.id} value={c.id}>
            {c.label}
          </option>
        ))}
      </select>

      {isLoading || !workbench ? (
        <Skeleton lines={6} />
      ) : (
        <>
          <Card>
            <h3>Proposed Fix</h3>
            <button
              className="btn btn-primary"
              disabled={generateMutation.isPending}
              onClick={() => generateMutation.mutate()}
            >
              Generate Fix
            </button>
            {error && <p style={{ color: "var(--severity-p0)" }}>{error}</p>}
            {!workbench.fix ? (
              <p className="text-dense">No fix proposed yet.</p>
            ) : (
              <>
                <p>
                  <strong>Type:</strong> {workbench.fix.fix_type} · <strong>Status:</strong> {workbench.fix.status}
                </p>
                <p className="text-dense">{workbench.fix.rationale}</p>
                <pre className="text-dense" style={{ background: "var(--color-panel-tint)", padding: 12 }}>
                  {workbench.fix.patch}
                </pre>
                <button
                  className="btn btn-primary"
                  disabled={workbench.cluster.is_p0 || regressionMutation.isPending}
                  title={
                    workbench.cluster.is_p0
                      ? "P0 findings require human acknowledgment before regression can run"
                      : undefined
                  }
                  onClick={() => regressionMutation.mutate()}
                >
                  Apply & Run Regression
                </button>
              </>
            )}
          </Card>

          {workbench.regression && (
            <Card>
              <h3>Regression Results</h3>
              <table className="al-table">
                <thead>
                  <tr>
                    <th>Dimension</th>
                    <th>Before</th>
                    <th>After</th>
                    <th>Delta</th>
                  </tr>
                </thead>
                <tbody>
                  {Array.from(
                    new Set([
                      ...Object.keys(workbench.regression.before_pass_rates),
                      ...Object.keys(workbench.regression.after_pass_rates),
                    ])
                  ).map((dim) => {
                    const before = workbench.regression!.before_pass_rates[dim];
                    const after = workbench.regression!.after_pass_rates[dim];
                    const delta = before != null && after != null ? after - before : null;
                    return (
                      <tr key={dim}>
                        <td>{dim}</td>
                        <td className="numeric">{before != null ? `${Math.round(before * 100)}%` : "—"}</td>
                        <td className="numeric">{after != null ? `${Math.round(after * 100)}%` : "—"}</td>
                        <td className="numeric">
                          {delta == null ? "—" : delta > 0 ? `▲ ${Math.round(delta * 100)}%` : delta < 0 ? `▼ ${Math.round(delta * 100)}%` : "—"}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
              <p className="text-dense">
                target: {workbench.regression.target_dimension} · regenerated batch: {workbench.regression.batch_id} ·
                n_before {workbench.regression.n_before} · n_after {workbench.regression.n_after}
              </p>
            </Card>
          )}
        </>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Verify the build**

```bash
cd frontend && npm run build
```
Expected: no TypeScript errors. Manually confirm cluster selection loads workbench state, "Apply & Run Regression" is disabled on P0 clusters. Skip clicking "Generate Fix"/"Apply & Run Regression" against a live model unless you intend to spend real LLM budget — same cost caveat as the original Streamlit page.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/routes/FixWorkbench.tsx
git commit -m "feat: Fix Workbench page (docs/superpowers/plans/2026-07-13-streamlit-to-web-migration.md)"
```

---

## Task 17: Jobs page

**Files:**
- Modify: `frontend/src/routes/Jobs.tsx`

**Interfaces:**
- Consumes: `fetchJobsStatus`, `fetchEvalEstimate`, `launchCorpusJob`, `launchEvalsJob`, `launchReclusterJob` from `api/client.ts`; `Card` from `components/`.

- [ ] **Step 1: Implement the page**

```tsx
// frontend/src/routes/Jobs.tsx
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  fetchEvalEstimate,
  fetchJobsStatus,
  launchCorpusJob,
  launchEvalsJob,
  launchReclusterJob,
} from "../api/client";
import { Card } from "../components/Card";
import { Skeleton } from "../components/Skeleton";

function summaryLine(finishedAt: string | null, summary: Record<string, unknown>, fields: string[]): string {
  if (!finishedAt) return "No completed runs yet.";
  const parts = [`Last run ${new Date(finishedAt).toLocaleString()}`];
  parts.push(...fields.map((f) => `${f}: ${summary[f] ?? "—"}`));
  return parts.join(" · ");
}

export function Jobs() {
  const queryClient = useQueryClient();
  const [count, setCount] = useState(60);
  const [failureRate, setFailureRate] = useState(30);
  const [scope, setScope] = useState<"unevaluated" | "full">("unevaluated");
  const [model, setModel] = useState("claude-haiku-4-5");
  const [message, setMessage] = useState<string | null>(null);

  const { data: status, isLoading } = useQuery({ queryKey: ["jobs-status"], queryFn: fetchJobsStatus });
  const { data: estimate } = useQuery({
    queryKey: ["eval-estimate", scope, model],
    queryFn: () => fetchEvalEstimate(scope, model),
  });

  const corpusMutation = useMutation({
    mutationFn: () => launchCorpusJob(count, failureRate / 100),
    onSuccess: () => {
      setMessage("Started generate_corpus — follow progress in the job log below.");
      queryClient.invalidateQueries({ queryKey: ["jobs-status"] });
    },
  });

  const evalsMutation = useMutation({
    mutationFn: () => launchEvalsJob(scope, model),
    onSuccess: () => {
      setMessage("Started run_evals — follow progress in the job log below.");
      queryClient.invalidateQueries({ queryKey: ["jobs-status"] });
    },
  });

  const reclusterMutation = useMutation({
    mutationFn: () => launchReclusterJob(),
    onSuccess: () => {
      setMessage("Started recluster — follow progress in the job log below.");
      queryClient.invalidateQueries({ queryKey: ["jobs-status"] });
    },
  });

  if (isLoading || !status) {
    return (
      <Card>
        <Skeleton lines={8} />
      </Card>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <h2>Jobs</h2>
      {message && <p className="text-dense">{message}</p>}

      <Card>
        <h3>Corpus Generation</h3>
        <label className="text-dense">
          Call count
          <input
            type="number"
            min={1}
            max={500}
            value={count}
            onChange={(e) => setCount(Number(e.target.value))}
            style={{ marginLeft: 8 }}
          />
        </label>
        <br />
        <label className="text-dense">
          Failure injection rate: {failureRate}%
          <input
            type="range"
            min={0}
            max={100}
            value={failureRate}
            onChange={(e) => setFailureRate(Number(e.target.value))}
            style={{ display: "block", width: "100%" }}
          />
        </label>
        <button className="btn btn-primary" onClick={() => corpusMutation.mutate()}>
          Generate Corpus
        </button>
        <p className="text-dense">
          {summaryLine(status.corpus.finished_at, status.corpus.summary, ["generated", "failed", "duration_ms"])}
        </p>
      </Card>

      <Card>
        <h3>Eval Run</h3>
        <div>
          <label className="text-dense">
            <input
              type="radio"
              checked={scope === "unevaluated"}
              onChange={() => setScope("unevaluated")}
            />{" "}
            Unevaluated only
          </label>{" "}
          <label className="text-dense">
            <input type="radio" checked={scope === "full"} onChange={() => setScope("full")} /> Full corpus
          </label>
        </div>
        <select className="select" value={model} onChange={(e) => setModel(e.target.value)}>
          <option value="claude-haiku-4-5">claude-haiku-4-5</option>
          <option value="claude-sonnet-5">claude-sonnet-5</option>
        </select>
        {estimate && (
          <p className="text-dense">
            Estimated: {estimate.n_calls} calls ≈ {(estimate.estimate_cents / 100).toFixed(2)} USD
          </p>
        )}
        <button className="btn btn-primary" onClick={() => evalsMutation.mutate()}>
          Run Evals
        </button>
        <p className="text-dense">
          {summaryLine(status.evals.finished_at, status.evals.summary, ["evaluated", "cost_cents", "duration_ms"])}
        </p>
      </Card>

      <Card>
        <h3>Clustering</h3>
        <button className="btn btn-primary" onClick={() => reclusterMutation.mutate()}>
          Re-cluster Failures
        </button>
        <p className="text-dense">
          {summaryLine(status.cluster.finished_at, status.cluster.summary, ["clusters", "failures", "cost_cents"])}
        </p>
      </Card>

      <Card>
        <h3>Job log</h3>
        <div style={{ maxHeight: 200, overflowY: "auto" }} className="text-dense">
          {status.log_lines.length ? status.log_lines.map((line, i) => <div key={i}>{line}</div>) : "No job log yet."}
        </div>
      </Card>
    </div>
  );
}
```

- [ ] **Step 2: Verify the build and manually check the flow**

```bash
cd frontend && npm run build
```
Expected: no TypeScript errors. With both servers running, open `http://localhost:5173/jobs`, click "Generate Corpus" with a small count (e.g. 5), and confirm the job log panel eventually shows output (poll by refreshing or add a manual refetch — automatic polling is not in scope for this plan) and the corpus summary line updates.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/routes/Jobs.tsx
git commit -m "feat: Jobs page (docs/superpowers/plans/2026-07-13-streamlit-to-web-migration.md)"
```

---

## Task 18: End-to-end verification, then remove Streamlit

**Files:**
- Delete: `agentlens/dashboard/app.py`, `agentlens/dashboard/ui.py`, `agentlens/dashboard/pages/` (entire directory)
- Modify: `pyproject.toml` (remove the `streamlit` dependency line)
- Modify: `README.md` (replace the `streamlit run` command with the two-terminal FastAPI + Vite instructions)
- Delete: `tests/test_dashboard_pages.py`, `tests/test_app_shell.py` if either imports `streamlit` or the removed page modules (confirm with the grep in Step 1 before deleting)

**Interfaces:** none — this task only removes dead code once the replacement is confirmed working.

- [ ] **Step 1: Confirm nothing outside `dashboard/` still imports the Streamlit page modules**

```bash
grep -rl "dashboard.app\|dashboard\.pages\|dashboard\.ui\b\|^import streamlit\|from streamlit" \
  --include="*.py" agentlens tests | grep -v "agentlens/dashboard/app.py\|agentlens/dashboard/ui.py\|agentlens/dashboard/pages"
```
Expected: no output (or only `tests/test_dashboard_pages.py` / `tests/test_app_shell.py`, which you'll delete alongside the Streamlit files if their only purpose was exercising the Streamlit pages — read them first to confirm before deleting).

- [ ] **Step 2: Full manual walkthrough with both servers running**

```bash
uv run uvicorn agentlens.api.main:app --reload --port 8000 &
cd frontend && npm run dev &
```

Open `http://localhost:5173` and, using a DB seeded via `uv run python -m agentlens.jobs.generate_corpus --count 20 --failure-rate 0.3` followed by `uv run python -m agentlens.jobs.run_evals --scope full --model claude-haiku-4-5` (costs real LLM budget — confirm with the user before running), walk the golden path from the 2026-07-10 UI design doc:

- Jobs → Conversations → Call Detail → Clusters → Fix Workbench
- Review Queue → Call Detail (read-only)
- Overview → Conversations (severity filter) and → Clusters (cluster filter)

Confirm every navigation, filter, and the Review Queue submit flow behaves as described in `docs/superpowers/specs/2026-07-10-ui-design.md`. Stop both servers afterward.

- [ ] **Step 3: Run the full backend test suite one more time**

```bash
uv run pytest -m "not llm" && uv run mypy agentlens/ && uv run ruff check --fix . && uv run ruff format .
```
Expected: all green.

- [ ] **Step 4: Remove the Streamlit dashboard**

```bash
git rm -r agentlens/dashboard/app.py agentlens/dashboard/ui.py agentlens/dashboard/pages
```

If `tests/test_dashboard_pages.py` or `tests/test_app_shell.py` only exercised the removed Streamlit pages (confirm by reading them), remove them too:

```bash
git rm tests/test_dashboard_pages.py tests/test_app_shell.py
```

- [ ] **Step 5: Remove the `streamlit` dependency**

Edit `pyproject.toml` and delete the `"streamlit>=1.59.1",` line from `dependencies`, then:

```bash
uv sync
```

- [ ] **Step 6: Update the README run instructions**

Replace any `uv run streamlit run agentlens/dashboard/app.py` line in `README.md` with:

```bash
uv run uvicorn agentlens.api.main:app --reload --port 8000   # backend, terminal 1
cd frontend && npm run dev                                    # frontend, terminal 2 (http://localhost:5173)
```

- [ ] **Step 7: Run the full test suite one final time to confirm nothing broke**

```bash
uv run pytest -m "not llm" && uv run mypy agentlens/
```
Expected: all green, no `agentlens.dashboard.app`/`ui`/`pages` import errors.

- [ ] **Step 8: Commit**

```bash
git add pyproject.toml uv.lock README.md
git commit -m "chore: remove Streamlit dashboard, migration to FastAPI+React complete (docs/superpowers/plans/2026-07-13-streamlit-to-web-migration.md)"
```

---

## Plan Self-Review Notes

- **Spec coverage:** Every endpoint/page in the design doc (`/api/status`, `/api/overview`, `/api/conversations` list+detail, `/api/clusters`, `/api/review-queue` GET+POST, `/api/fix-workbench` GET+2×POST, `/api/jobs` status+estimate+3×launch) has a task; every one of the 7 Streamlit pages has a corresponding React route; the design-token palette, button shape, and Apple-style font stack from the approved design doc are encoded in Task 9's `tokens.css` and Task 10's `components.css`.
- **P0 gating:** enforced server-side in Task 7 (`apply_regression` 400s on a P0 cluster) in addition to the client-side disabled button in Task 16 — matches the Global Constraints requirement that this isn't purely a UI-layer guard.
- **Role model:** preserved via `RoleContext` (Task 11) with the same `PAGES_BY_ROLE` mapping as the original `agentlens/dashboard/app.py`.
- **Session-state → URL migration:** `selected_call_id` → `/calls/:callId` route param; `call_detail_origin` → `?from=` query param; filter state (severity/dimension/cluster/outcome, routing/severity, cluster focus) → query params in Conversations/Clusters; `fix_cluster_id` → `?cluster_id=` query param on Fix Workbench — all explicitly covered in Tasks 13, 14, 16.
