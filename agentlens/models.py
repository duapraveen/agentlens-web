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
