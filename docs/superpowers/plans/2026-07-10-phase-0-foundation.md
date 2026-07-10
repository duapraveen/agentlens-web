# Phase 0 — Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Project skeleton every later phase builds on: tooling, typed settings, database + core ORM models, the redaction boundary, and the LLM gateway — with zero real API calls (gateway tested against mocks; one real-API smoke test exists but is `llm`-marked and not run).

**Architecture:** Monorepo package `agentlens/` (constitution Article II). `agentlens/llm/gateway.py` is the only module that imports the anthropic SDK: it redacts outbound text, validates structured JSON via `client.messages.parse` + Pydantic, records cost in USD cents to `llm_call_log`, and records unparseable output/refusals as failures. SQLAlchemy 2.0 ORM with portable column types only.

**Tech Stack:** Python 3.11+, uv, SQLAlchemy 2.0, Pydantic v2 + pydantic-settings, anthropic SDK, structlog (dependency declared now, used in Phase 1 jobs), pytest, ruff, mypy --strict.

**Tasks:** T001–T005 from `specs/001-agentlens-core/tasks.md`.

## Global Constraints

- mypy --strict clean; docstrings state units (scores 0-100, costs USD cents, durations ms).
- ruff check + format clean.
- All LLM calls through the gateway; unparseable output is a recorded failure.
- Outbound transcript text passes through `privacy/redact.py` (enforced inside the gateway).
- No transcript content in logs. SQLAlchemy ORM only; Postgres-portable types.
- Secrets via env; `.env` gitignored; `.env.example` current.
- `llm`-marked tests are never run without explicit user approval.
- Conventional Commits referencing task IDs; end commits with `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.

Pricing cached from Anthropic docs 2026-07-10 (sticker, USD cents per MTok in/out): `claude-haiku-4-5` = (100, 500); `claude-sonnet-5` = (300, 1500).

---

### Task 1: Project scaffold (T001)

**Files:**
- Create: `pyproject.toml`, `.gitignore`, `.env.example`, `agentlens/__init__.py`, `docs/adr/001-initial-stack.md`

**Interfaces:** Produces the tooling every later task runs under (`uv run pytest/ruff/mypy`, `llm` marker).

- [ ] **Step 1: git init and write files**

```bash
git init -b main
```

`pyproject.toml`:

```toml
[project]
name = "agentlens"
version = "0.1.0"
description = "AI conversation quality and observability platform for healthcare voice agents"
requires-python = ">=3.11"
dependencies = [
    "anthropic>=0.116",
    "pydantic>=2.7",
    "pydantic-settings>=2.2",
    "sqlalchemy>=2.0.30",
    "structlog>=24.1",
]

[dependency-groups]
dev = ["pytest>=8.0", "ruff>=0.4", "mypy>=1.10"]

[tool.pytest.ini_options]
markers = [
    "llm: calls the real Anthropic API and costs money (excluded from the fast suite)",
]

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "SIM"]

[tool.mypy]
strict = true
packages = ["agentlens"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["agentlens"]
```

`.gitignore`:

```gitignore
.venv/
__pycache__/
*.pyc
.env
.pytest_cache/
.mypy_cache/
.ruff_cache/
logs/
data/*
!data/golden/
*.egg-info/
dist/
```

`.env.example`:

```bash
# Anthropic API key used by the LLM gateway.
ANTHROPIC_API_KEY=sk-ant-...

# Optional overrides (defaults shown):
# AGENTLENS_DATABASE_URL=sqlite:///data/agentlens.db
# AGENTLENS_GOLDEN_DIR=data/golden
# AGENTLENS_JOBS_LOG_PATH=logs/jobs.log
# AGENTLENS_GENERATOR_MODEL=claude-sonnet-5
# AGENTLENS_JUDGE_MODEL=claude-haiku-4-5
```

`agentlens/__init__.py`:

```python
"""AgentLens: conversation quality and observability platform (synthetic data only)."""
```

`docs/adr/001-initial-stack.md`:

```markdown
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
```

- [ ] **Step 2: Sync and verify tooling**

Run: `uv sync && uv run pytest --collect-only -q; uv run ruff check . && uv run mypy agentlens/`
Expected: sync succeeds; pytest collects 0 items without error; ruff/mypy clean.

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "feat: project scaffold and ADR-001 (specs/001-agentlens-core/tasks.md#T001)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 2: Typed settings (T002)

**Files:**
- Create: `agentlens/config.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Produces `Settings` (fields: `anthropic_api_key: str` via alias `ANTHROPIC_API_KEY`; prefix `AGENTLENS_` for `database_url: str`, `golden_dir: Path`, `jobs_log_path: Path`, `generator_model: str`, `judge_model: str`) and `get_settings() -> Settings`. All later code reads config only through `get_settings()`.

- [ ] **Step 1: Write the failing test**

`tests/test_config.py`:

```python
"""Tests for typed settings."""

from pathlib import Path

import pytest

from agentlens.config import Settings, get_settings


def test_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    assert settings.database_url == "sqlite:///data/agentlens.db"
    assert settings.golden_dir == Path("data/golden")
    assert settings.jobs_log_path == Path("logs/jobs.log")
    assert settings.generator_model == "claude-sonnet-5"
    assert settings.judge_model == "claude-haiku-4-5"
    assert settings.anthropic_api_key == ""


def test_env_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENTLENS_DATABASE_URL", "sqlite:///tmp/other.db")
    monkeypatch.setenv("AGENTLENS_JUDGE_MODEL", "claude-sonnet-5")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    settings = get_settings()
    assert settings.database_url == "sqlite:///tmp/other.db"
    assert settings.judge_model == "claude-sonnet-5"
    assert settings.anthropic_api_key == "sk-test"
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_config.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'agentlens.config'`

- [ ] **Step 3: Implement**

`agentlens/config.py`:

```python
"""Typed application settings loaded from environment variables (and .env)."""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings.

    Conventions: costs are USD cents, durations are ms, scores are 0-100.
    App fields read the ``AGENTLENS_`` env prefix; the API key reads the
    standard ``ANTHROPIC_API_KEY`` so the anthropic SDK convention holds.
    """

    model_config = SettingsConfigDict(env_prefix="AGENTLENS_", env_file=".env", extra="ignore")

    anthropic_api_key: str = Field(default="", validation_alias="ANTHROPIC_API_KEY")
    database_url: str = "sqlite:///data/agentlens.db"
    golden_dir: Path = Path("data/golden")
    jobs_log_path: Path = Path("logs/jobs.log")
    generator_model: str = "claude-sonnet-5"
    judge_model: str = "claude-haiku-4-5"


def get_settings() -> Settings:
    """Load settings fresh from the environment. Cheap; call at use sites, don't cache."""
    return Settings()
```

- [ ] **Step 4: Verify**

Run: `uv run pytest tests/test_config.py -v && uv run ruff check --fix . && uv run ruff format . && uv run mypy agentlens/`
Expected: 2 passed; ruff/mypy clean.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat: typed settings (specs/001-agentlens-core/tasks.md#T002)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 3: DB engine + core ORM models (T003)

**Files:**
- Create: `agentlens/models.py`, `agentlens/db.py`
- Test: `tests/conftest.py`, `tests/test_models.py`

**Interfaces:**
- Produces `Base`, `Call`, `GroundTruthLabel`, `LLMCallLog`, `JobRun`, `utcnow()`; `create_db_engine(url: str | None = None) -> Engine`; `open_session(url: str | None = None) -> Session`; shared `db_session` fixture (file-backed tmp SQLite) for all later test files.

- [ ] **Step 1: Write the failing tests**

`tests/conftest.py`:

```python
"""Shared test fixtures."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from agentlens.models import Base


@pytest.fixture()
def db_session(tmp_path: Path) -> Iterator[Session]:
    """A Session bound to a fresh file-backed SQLite database in tmp_path."""
    engine = create_engine(f"sqlite:///{tmp_path}/test.db")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
```

`tests/test_models.py`:

```python
"""Tests for ORM models and engine helpers."""

from pathlib import Path

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from agentlens.db import create_db_engine, open_session
from agentlens.models import Call, GroundTruthLabel, JobRun, LLMCallLog


def _make_call(call_id: str = "call_abc123") -> Call:
    return Call(
        id=call_id,
        scenario="symptom_triage",
        transcript=[
            {"speaker": "patient", "text": "I have a headache."},
            {"speaker": "agent", "text": "How long has it lasted?"},
        ],
        batch_id="batch_1",
    )


def test_call_roundtrip(db_session: Session) -> None:
    db_session.add(_make_call())
    db_session.commit()
    loaded = db_session.get(Call, "call_abc123")
    assert loaded is not None
    assert loaded.transcript[0]["speaker"] == "patient"
    assert loaded.is_golden is False
    assert loaded.agent_prompt_version == "v1"
    assert loaded.ground_truth is None


def test_ground_truth_label_links_to_call(db_session: Session) -> None:
    call = _make_call()
    db_session.add(call)
    db_session.add(
        GroundTruthLabel(
            call_id=call.id,
            failure_mode="missed_escalation",
            pipeline_stage="reasoning",
            severity="P0",
        )
    )
    db_session.commit()
    assert call.ground_truth is not None
    assert call.ground_truth.severity == "P0"


def test_one_label_per_call(db_session: Session) -> None:
    call = _make_call()
    db_session.add(call)
    for _ in range(2):
        db_session.add(
            GroundTruthLabel(
                call_id=call.id,
                failure_mode="dead_end_loop",
                pipeline_stage="orchestration",
                severity="P1",
            )
        )
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_llm_call_log_and_job_run(db_session: Session) -> None:
    db_session.add(
        LLMCallLog(
            purpose="corpus_generation",
            model="claude-sonnet-5",
            prompt_name="corpus_generation",
            prompt_version="1.0",
            input_tokens=100,
            output_tokens=500,
            cost_cents=0.105,
            success=True,
        )
    )
    db_session.add(JobRun(job_name="generate_corpus", status="running", summary={}))
    db_session.commit()
    log = db_session.query(LLMCallLog).one()
    assert log.cost_cents == pytest.approx(0.105)
    run = db_session.query(JobRun).one()
    assert run.finished_at is None


def test_create_db_engine_creates_sqlite_parent_dir(tmp_path: Path) -> None:
    url = f"sqlite:///{tmp_path}/nested/dir/app.db"
    create_db_engine(url)
    assert (tmp_path / "nested" / "dir" / "app.db").exists()


def test_open_session_usable(tmp_path: Path) -> None:
    with open_session(f"sqlite:///{tmp_path}/s.db") as session:
        session.add(_make_call("call_open"))
        session.commit()
        assert session.get(Call, "call_open") is not None
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/test_models.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'agentlens.models'`

- [ ] **Step 3: Implement**

`agentlens/models.py`:

```python
"""SQLAlchemy 2.0 ORM models.

Conventions: costs in USD cents, durations in ms, scores 0-100.
Uses only portable column types (String, JSON, DateTime, ...) so the schema
ports to Postgres with zero code change. No transcript text is ever logged
from these models — log IDs and metadata only.
"""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    """Timezone-aware current UTC time (default factory for created_at columns)."""
    return datetime.now(UTC)


class Base(DeclarativeBase):
    """Declarative base for all AgentLens tables."""


class Call(Base):
    """One synthetic patient-agent conversation."""

    __tablename__ = "calls"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    scenario: Mapped[str] = mapped_column(String(64), index=True)
    transcript: Mapped[list[dict[str, Any]]] = mapped_column(JSON)
    batch_id: Mapped[str] = mapped_column(String(40), index=True)
    agent_prompt_version: Mapped[str] = mapped_column(String(16), default="v1")
    is_golden: Mapped[bool] = mapped_column(default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    ground_truth: Mapped["GroundTruthLabel | None"] = relationship(back_populates="call")


class GroundTruthLabel(Base):
    """Injected-failure ground truth, stored separately from eval outputs (AC-7.3)."""

    __tablename__ = "ground_truth_labels"
    __table_args__ = (UniqueConstraint("call_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    call_id: Mapped[str] = mapped_column(ForeignKey("calls.id"))
    failure_mode: Mapped[str] = mapped_column(String(64), index=True)
    pipeline_stage: Mapped[str] = mapped_column(String(32))
    severity: Mapped[str] = mapped_column(String(4))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    call: Mapped[Call] = relationship(back_populates="ground_truth")


class LLMCallLog(Base):
    """One row per gateway LLM call: cost accounting and failure recording."""

    __tablename__ = "llm_call_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    purpose: Mapped[str] = mapped_column(String(64), index=True)
    model: Mapped[str] = mapped_column(String(64))
    prompt_name: Mapped[str] = mapped_column(String(64))
    prompt_version: Mapped[str] = mapped_column(String(16))
    input_tokens: Mapped[int] = mapped_column(default=0)
    output_tokens: Mapped[int] = mapped_column(default=0)
    cost_cents: Mapped[float] = mapped_column(default=0.0)
    success: Mapped[bool] = mapped_column(default=True)
    error: Mapped[str | None] = mapped_column(Text, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class JobRun(Base):
    """One row per batch-job invocation; drives the dashboard's last-run summaries."""

    __tablename__ = "job_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_name: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(16), default="running")
    summary: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
```

`agentlens/db.py`:

```python
"""Engine and session helpers. All DB access goes through the ORM (no raw SQL)."""

from pathlib import Path

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session

from agentlens.config import get_settings
from agentlens.models import Base


def create_db_engine(url: str | None = None) -> Engine:
    """Create an engine for `url` (default: settings) and ensure the schema exists."""
    resolved = url or get_settings().database_url
    if resolved.startswith("sqlite:///"):
        db_path = Path(resolved.removeprefix("sqlite:///"))
        db_path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(resolved)
    Base.metadata.create_all(engine)
    return engine


def open_session(url: str | None = None) -> Session:
    """A new Session bound to a fresh engine. Use as a context manager."""
    return Session(create_db_engine(url))
```

- [ ] **Step 4: Verify**

Run: `uv run pytest tests/test_models.py -v && uv run ruff check --fix . && uv run ruff format . && uv run mypy agentlens/`
Expected: 6 passed; ruff/mypy clean.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat: core ORM models and db helpers (specs/001-agentlens-core/tasks.md#T003)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 4: Privacy redaction module (T004)

**Files:**
- Create: `agentlens/privacy/__init__.py`, `agentlens/privacy/redact.py`
- Test: `tests/test_redact.py`

**Interfaces:**
- Produces `redact(text: str) -> str`. The gateway (T005) calls it on all outbound user content unconditionally.

- [ ] **Step 1: Write the failing tests**

`tests/test_redact.py`:

```python
"""Tests for the redaction boundary (synthetic examples only)."""

from agentlens.privacy.redact import redact


def test_redacts_ssn() -> None:
    assert redact("SSN is 123-45-6789 ok") == "SSN is [REDACTED:SSN] ok"


def test_redacts_phone() -> None:
    assert redact("call me at (555) 123-4567") == "call me at [REDACTED:PHONE]"
    assert redact("call 555-123-4567 now") == "call [REDACTED:PHONE] now"


def test_redacts_email() -> None:
    assert redact("mail pat.doe@example.com please") == "mail [REDACTED:EMAIL] please"


def test_redacts_date_of_birth_style_dates() -> None:
    assert redact("DOB 03/14/1985 noted") == "DOB [REDACTED:DATE] noted"
    assert redact("born 1985-03-14") == "born [REDACTED:DATE]"


def test_redacts_mrn() -> None:
    assert redact("MRN 84921 on file") == "[REDACTED:MRN] on file"
    assert redact("mrn: 84921") == "[REDACTED:MRN]"


def test_plain_text_passes_through() -> None:
    text = "I would like to book an appointment for next Tuesday."
    assert redact(text) == text
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/test_redact.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'agentlens.privacy'`

- [ ] **Step 3: Implement**

`agentlens/privacy/__init__.py` (empty) and `agentlens/privacy/redact.py`:

```python
"""Redaction boundary for transcript text bound to external APIs.

All data in this repo is synthetic, but the architecture must be
HIPAA-plausible (constitution V.2): every code path that sends transcript
text to an external API calls redact() first. Pattern order matters —
more specific patterns (SSN, MRN) run before generic ones (phone, date).
"""

import re

_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "[REDACTED:SSN]"),
    (re.compile(r"\bmrn\s*:?\s*\d+\b", re.IGNORECASE), "[REDACTED:MRN]"),
    (re.compile(r"\(\d{3}\)\s*\d{3}-\d{4}"), "[REDACTED:PHONE]"),
    (re.compile(r"\b\d{3}-\d{3}-\d{4}\b"), "[REDACTED:PHONE]"),
    (
        re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
        "[REDACTED:EMAIL]",
    ),
    (re.compile(r"\b\d{1,2}/\d{1,2}/\d{4}\b"), "[REDACTED:DATE]"),
    (re.compile(r"\b\d{4}-\d{2}-\d{2}\b"), "[REDACTED:DATE]"),
]


def redact(text: str) -> str:
    """Replace PHI-shaped substrings (SSN, MRN, phone, email, dates) with placeholders."""
    for pattern, replacement in _PATTERNS:
        text = pattern.sub(replacement, text)
    return text
```

- [ ] **Step 4: Verify**

Run: `uv run pytest tests/test_redact.py -v && uv run ruff check --fix . && uv run ruff format . && uv run mypy agentlens/`
Expected: 6 passed; ruff/mypy clean.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat: privacy redaction boundary (specs/001-agentlens-core/tasks.md#T004)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 5: LLM gateway (T005)

**Files:**
- Create: `agentlens/llm/__init__.py`, `agentlens/llm/gateway.py`
- Test: `tests/test_gateway.py`

**Interfaces:**
- Consumes `redact` (T004), `LLMCallLog` (T003), `get_settings` (T002).
- Produces:
  - `GatewayResult[T]`: `parsed: T | None`, `success: bool`, `error: str | None`, `cost_cents: float`.
  - `complete_json(session, *, purpose, prompt_name, prompt_version, system, user_content, response_model, model, max_tokens=8192, client=None) -> GatewayResult[T]` — the only function allowed to touch the anthropic SDK; `client` injectable for tests; commits one `LLMCallLog` row per call (success or failure). Callers must invoke it before staging their own uncommitted objects.
  - `cost_cents(model: str, input_tokens: int, output_tokens: int) -> float` (USD cents; raises for unpriced models).

- [ ] **Step 1: Write the failing tests**

`tests/test_gateway.py`:

```python
"""Tests for the LLM gateway (mocked anthropic client; one real-API test marked llm)."""

from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest
from pydantic import BaseModel
from sqlalchemy.orm import Session

from agentlens.llm.gateway import GatewayResult, complete_json, cost_cents
from agentlens.models import LLMCallLog


class Answer(BaseModel):
    value: int


def _mock_client(
    *, parsed: Any = None, stop_reason: str = "end_turn", raises: Exception | None = None
) -> MagicMock:
    client = MagicMock()
    if raises is not None:
        client.messages.parse.side_effect = raises
    else:
        client.messages.parse.return_value = SimpleNamespace(
            parsed_output=parsed,
            stop_reason=stop_reason,
            usage=SimpleNamespace(input_tokens=1000, output_tokens=2000),
        )
    return client


def _call(session: Session, client: MagicMock) -> GatewayResult[Answer]:
    return complete_json(
        session,
        purpose="test",
        prompt_name="test_prompt",
        prompt_version="1.0",
        system="You are a test.",
        user_content="What is 2+2? My SSN is 123-45-6789.",
        response_model=Answer,
        model="claude-haiku-4-5",
        client=client,
    )


def test_cost_cents_known_models() -> None:
    # haiku: 100 cents/MTok in, 500 cents/MTok out
    assert cost_cents("claude-haiku-4-5", 1_000_000, 1_000_000) == pytest.approx(600.0)
    assert cost_cents("claude-sonnet-5", 1_000_000, 0) == pytest.approx(300.0)


def test_cost_cents_unknown_model_raises() -> None:
    with pytest.raises(ValueError, match="no pricing"):
        cost_cents("claude-unknown-9", 1, 1)


def test_success_parses_logs_and_costs(db_session: Session) -> None:
    client = _mock_client(parsed=Answer(value=4))
    result = _call(db_session, client)
    assert result.success and result.parsed == Answer(value=4)
    assert result.cost_cents == pytest.approx(0.1 + 1.0)  # 1000 in + 2000 out on haiku
    log = db_session.query(LLMCallLog).one()
    assert log.success is True
    assert log.cost_cents == pytest.approx(result.cost_cents)
    assert log.purpose == "test"


def test_outbound_content_is_redacted(db_session: Session) -> None:
    client = _mock_client(parsed=Answer(value=4))
    _call(db_session, client)
    sent = client.messages.parse.call_args.kwargs["messages"][0]["content"]
    assert "123-45-6789" not in sent
    assert "[REDACTED:SSN]" in sent


def test_unparseable_output_is_recorded_failure(db_session: Session) -> None:
    client = _mock_client(parsed=None)
    result = _call(db_session, client)
    assert not result.success and result.parsed is None
    log = db_session.query(LLMCallLog).one()
    assert log.success is False
    assert log.error is not None


def test_api_error_is_recorded_failure(db_session: Session) -> None:
    client = _mock_client(raises=RuntimeError("boom"))
    result = _call(db_session, client)
    assert not result.success
    assert "boom" in (result.error or "")
    assert db_session.query(LLMCallLog).one().success is False


def test_refusal_is_recorded_failure(db_session: Session) -> None:
    client = _mock_client(parsed=None, stop_reason="refusal")
    result = _call(db_session, client)
    assert not result.success
    assert "refusal" in (result.error or "")


@pytest.mark.llm
def test_real_api_smoke(db_session: Session) -> None:
    """Costs money. Run only with explicit user approval: uv run pytest -m llm."""
    result = complete_json(
        db_session,
        purpose="smoke",
        prompt_name="smoke",
        prompt_version="1.0",
        system="Answer with the requested JSON only.",
        user_content="Return value=4.",
        response_model=Answer,
        model="claude-haiku-4-5",
    )
    assert result.success and result.parsed is not None and result.parsed.value == 4
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/test_gateway.py -m "not llm" -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'agentlens.llm'`

- [ ] **Step 3: Implement**

`agentlens/llm/__init__.py` (empty) and `agentlens/llm/gateway.py`:

```python
"""Single entry point for all LLM calls.

Responsibilities (constitution II): redact outbound text, validate structured
JSON output with Pydantic, account cost in USD cents, tag prompt versions,
and record every call — including unparseable output — as an LLMCallLog row.
Transport retries use the anthropic SDK's built-in budget (max_retries=2);
parse/validation failures are recorded, never retried.

No other module may import the anthropic SDK.
"""

from dataclasses import dataclass
from typing import Generic, TypeVar

import anthropic
from pydantic import BaseModel
from sqlalchemy.orm import Session

from agentlens.config import get_settings
from agentlens.models import LLMCallLog
from agentlens.privacy.redact import redact

T = TypeVar("T", bound=BaseModel)

# Sticker prices cached from Anthropic docs 2026-07-10, USD cents per million
# tokens (input, output). Sonnet 5 has intro pricing (200/1000) through
# 2026-08-31; we use sticker prices and accept slight over-reporting.
_PRICING_CENTS_PER_MTOK: dict[str, tuple[float, float]] = {
    "claude-haiku-4-5": (100.0, 500.0),
    "claude-sonnet-5": (300.0, 1500.0),
}


def cost_cents(model: str, input_tokens: int, output_tokens: int) -> float:
    """Cost of one LLM call in USD cents. Raises ValueError for unpriced models."""
    if model not in _PRICING_CENTS_PER_MTOK:
        raise ValueError(f"no pricing for model {model!r}; add it to _PRICING_CENTS_PER_MTOK")
    in_rate, out_rate = _PRICING_CENTS_PER_MTOK[model]
    return input_tokens * in_rate / 1_000_000 + output_tokens * out_rate / 1_000_000


@dataclass(frozen=True)
class GatewayResult(Generic[T]):
    """Outcome of one gateway call. cost_cents is USD cents (0.0 if the call never ran)."""

    parsed: T | None
    success: bool
    error: str | None
    cost_cents: float


def _default_client() -> anthropic.Anthropic:
    settings = get_settings()
    return anthropic.Anthropic(api_key=settings.anthropic_api_key or None)


def complete_json(
    session: Session,
    *,
    purpose: str,
    prompt_name: str,
    prompt_version: str,
    system: str,
    user_content: str,
    response_model: type[T],
    model: str,
    max_tokens: int = 8192,
    client: anthropic.Anthropic | None = None,
) -> GatewayResult[T]:
    """Run one structured-JSON LLM call and log it (commits one LLMCallLog row).

    user_content is redacted unconditionally before leaving the process.
    Returns a failed GatewayResult (never raises) on API errors, refusals,
    or output that does not validate against response_model. Callers must
    invoke the gateway before staging their own uncommitted objects (the
    gateway commits the session).
    """
    client = client or _default_client()
    parsed: T | None = None
    error: str | None = None
    in_tokens = out_tokens = 0
    try:
        response = client.messages.parse(
            model=model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": redact(user_content)}],
            output_format=response_model,
        )
        in_tokens = response.usage.input_tokens
        out_tokens = response.usage.output_tokens
        if response.stop_reason == "refusal":
            error = "model returned stop_reason=refusal"
        elif response.parsed_output is None:
            error = "output did not validate against response model"
        else:
            parsed = response.parsed_output
    except Exception as exc:  # gateway boundary: every failure becomes a recorded result
        error = f"{type(exc).__name__}: {exc}"

    cents = cost_cents(model, in_tokens, out_tokens)
    session.add(
        LLMCallLog(
            purpose=purpose,
            model=model,
            prompt_name=prompt_name,
            prompt_version=prompt_version,
            input_tokens=in_tokens,
            output_tokens=out_tokens,
            cost_cents=cents,
            success=error is None,
            error=error,
        )
    )
    session.commit()
    return GatewayResult(parsed=parsed, success=error is None, error=error, cost_cents=cents)
```

- [ ] **Step 4: Verify (do NOT run the llm-marked test)**

Run: `uv run pytest -m "not llm" -v && uv run ruff check --fix . && uv run ruff format . && uv run mypy agentlens/`
Expected: full fast suite passes (7 gateway tests + earlier tests; 1 deselected); ruff/mypy clean.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat: LLM gateway with cost accounting and failure recording (specs/001-agentlens-core/tasks.md#T005)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

## Phase 0 Exit Gate

- `uv run pytest -m "not llm"` fully green (llm smoke test deselected, not run).
- `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy agentlens/` all clean.
- Zero API spend.
- Update `specs/001-agentlens-core/tasks.md` statuses T001–T005 → ☑ and commit.
