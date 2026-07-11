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
    eval_records: Mapped[list["EvalRecord"]] = relationship(back_populates="call")
    check_results: Mapped[list["DeterministicCheckResult"]] = relationship(back_populates="call")


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


class EvalRecord(Base):
    """One judge verdict for one call on one dimension (AC-1.1).

    Scores are 0-100; severity is P0/P1/P2 or "none"; passed is derived
    (severity == "none"). Provenance (AC-1.3): judge_model, prompt_version,
    rubric_version, input_hash. The unique constraint makes re-runs
    idempotent per judge configuration (AC-1.4).
    """

    __tablename__ = "eval_records"
    __table_args__ = (UniqueConstraint("call_id", "dimension", "judge_model", "prompt_version"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    call_id: Mapped[str] = mapped_column(ForeignKey("calls.id"), index=True)
    dimension: Mapped[str] = mapped_column(String(32), index=True)
    score: Mapped[int] = mapped_column()
    severity: Mapped[str] = mapped_column(String(8), index=True)
    passed: Mapped[bool] = mapped_column(index=True)
    failure_description: Mapped[str | None] = mapped_column(Text, default=None)
    judge_reasoning: Mapped[str] = mapped_column(Text, default="")
    pipeline_stage: Mapped[str | None] = mapped_column(String(32), default=None)
    judge_model: Mapped[str] = mapped_column(String(64))
    prompt_version: Mapped[str] = mapped_column(String(16))
    rubric_version: Mapped[str] = mapped_column(String(16))
    input_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    call: Mapped[Call] = relationship(back_populates="eval_records")
    review: Mapped["Review | None"] = relationship(back_populates="eval_record")


class Review(Base):
    """One human verdict on one judge finding (AC-4.1).

    At most one review per finding (unique eval_record_id); the reviewer's
    latest verdict wins — resubmission updates the row in place.
    """

    __tablename__ = "reviews"
    __table_args__ = (UniqueConstraint("eval_record_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    eval_record_id: Mapped[int] = mapped_column(ForeignKey("eval_records.id"))
    verdict: Mapped[str] = mapped_column(String(8))
    note: Mapped[str | None] = mapped_column(Text, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    eval_record: Mapped[EvalRecord] = relationship(back_populates="review")


class DeterministicCheckResult(Base):
    """Rule-based safety check outcome, independent of the LLM judge (AC-1.2).

    A triggered P0 check stands even when the judge scores the call clean
    (constitution I.3). Unique per (call, check) so re-runs are idempotent.
    """

    __tablename__ = "deterministic_check_results"
    __table_args__ = (UniqueConstraint("call_id", "check_name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    call_id: Mapped[str] = mapped_column(ForeignKey("calls.id"), index=True)
    check_name: Mapped[str] = mapped_column(String(64))
    triggered: Mapped[bool] = mapped_column(index=True)
    detail: Mapped[str | None] = mapped_column(Text, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    call: Mapped[Call] = relationship(back_populates="check_results")


class Cluster(Base):
    """One recurring failure pattern (derived data — rebuilt on every recluster run)."""

    __tablename__ = "clusters"

    id: Mapped[int] = mapped_column(primary_key=True)
    label: Mapped[str] = mapped_column(String(128))
    description: Mapped[str] = mapped_column(Text, default="")
    routing_suggestion: Mapped[str] = mapped_column(String(32))
    dominant_severity: Mapped[str] = mapped_column(String(4))
    size: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    members: Mapped[list["ClusterMember"]] = relationship(back_populates="cluster")
    fix_proposals: Mapped[list["FixProposal"]] = relationship(back_populates="cluster")


class ClusterMember(Base):
    """Membership of one failed eval record in one cluster."""

    __tablename__ = "cluster_members"
    __table_args__ = (UniqueConstraint("eval_record_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    cluster_id: Mapped[int] = mapped_column(ForeignKey("clusters.id"), index=True)
    eval_record_id: Mapped[int] = mapped_column(ForeignKey("eval_records.id"))

    cluster: Mapped[Cluster] = relationship(back_populates="members")
    eval_record: Mapped[EvalRecord] = relationship()


class FixProposal(Base):
    """One drafted fix for one cluster (AC-5.1).

    Lifecycle: proposed -> validated (regression ran) -> closed. Closing a
    fix on a P0 cluster requires a human actor (constitution V.4) — the
    guard lives in fixes/report.py :: close_fix.
    """

    __tablename__ = "fix_proposals"

    id: Mapped[int] = mapped_column(primary_key=True)
    cluster_id: Mapped[int] = mapped_column(ForeignKey("clusters.id"), index=True)
    fix_type: Mapped[str] = mapped_column(String(32))
    rationale: Mapped[str] = mapped_column(Text)
    patch: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default="proposed")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    cluster: Mapped[Cluster] = relationship(back_populates="fix_proposals")
    regression_runs: Mapped[list["RegressionRun"]] = relationship(back_populates="fix_proposal")


class RegressionRun(Base):
    """One before/after regression measurement for one fix (AC-5.2, AC-5.3).

    Pass rates are 0-1 fractions per dimension. regressed_dimensions lists
    non-target dimensions whose after-rate dropped below the before-rate.
    """

    __tablename__ = "regression_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    fix_proposal_id: Mapped[int] = mapped_column(ForeignKey("fix_proposals.id"), index=True)
    batch_id: Mapped[str] = mapped_column(String(40))
    n_before: Mapped[int] = mapped_column()
    n_after: Mapped[int] = mapped_column()
    before_pass_rates: Mapped[dict[str, Any]] = mapped_column(JSON)
    after_pass_rates: Mapped[dict[str, Any]] = mapped_column(JSON)
    target_dimension: Mapped[str] = mapped_column(String(32))
    regressed_dimensions: Mapped[list[str]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    fix_proposal: Mapped[FixProposal] = relationship(back_populates="regression_runs")


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
