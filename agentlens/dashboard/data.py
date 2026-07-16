"""Dashboard query layer: plain ORM functions, no Streamlit imports.

All dashboard DB reads live here so they stay unit-testable and raw-SQL-free.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from agentlens.corpus.scenarios import Dimension
from agentlens.models import (
    Call,
    Cluster,
    ClusterMember,
    DeterministicCheckResult,
    EvalRecord,
    FixProposal,
    GroundTruthLabel,
    JobRun,
    LLMCallLog,
    RegressionRun,
    utcnow,
)
from agentlens.prompts.judge import PROMPT_VERSION

_DIMENSION_ORDER = [d.value for d in Dimension]
_SEVERITY_ORDER = ["P0", "P1", "P2"]


def _severity_rank(severity: str) -> int:
    """Sort rank for a severity string: P0=0, P1=1, P2=2, anything else last."""
    return _SEVERITY_ORDER.index(severity) if severity in _SEVERITY_ORDER else len(_SEVERITY_ORDER)


@dataclass(frozen=True)
class StatusSummary:
    """Sidebar status block numbers."""

    last_eval_at: datetime | None
    n_calls: int
    n_golden: int


def status_summary(session: Session) -> StatusSummary:
    """Last completed eval run timestamp plus corpus/golden call counts."""
    last_eval = (
        session.query(JobRun)
        .filter(JobRun.job_name == "run_evals", JobRun.status == "completed")
        .order_by(JobRun.finished_at.desc())
        .first()
    )
    return StatusSummary(
        last_eval_at=last_eval.finished_at if last_eval else None,
        n_calls=session.query(Call).count(),
        n_golden=session.query(Call).filter(Call.is_golden).count(),
    )


def last_job_run(session: Session, job_name: str) -> JobRun | None:
    """Latest completed run of one job, for the per-card summary lines."""
    return (
        session.query(JobRun)
        .filter(JobRun.job_name == job_name, JobRun.status == "completed")
        .order_by(JobRun.id.desc())
        .first()
    )


def tail_log(path: Path, n: int = 20) -> list[str]:
    """Last n non-empty lines of the jobs log; empty list when the file is missing."""
    if not path.exists():
        return []
    lines = [line for line in path.read_text().splitlines() if line.strip()]
    return lines[-n:]


@dataclass(frozen=True)
class ConversationRow:
    """One evaluated call in the Conversations table."""

    call_id: str
    scenario: str
    failed_dimensions: set[str]
    has_p0: bool
    avg_score: float
    est_cost_cents: float
    created_at: datetime
    is_golden: bool


def _avg_judge_cost_cents(session: Session) -> float:
    """Global average judge cost per evaluated call (per-call lineage isn't stored)."""
    rows = session.query(LLMCallLog).filter(LLMCallLog.purpose == "judge", LLMCallLog.success)
    total = sum(r.cost_cents for r in rows)
    n_calls = session.query(EvalRecord.call_id).distinct().count()
    return total / n_calls if n_calls else 0.0


def conversation_rows(
    session: Session,
    severity: str | None = None,
    dimension: str | None = None,
    cluster_id: int | None = None,
    outcome: Literal["pass", "fail"] | None = None,
) -> list[ConversationRow]:
    """Evaluated calls with per-call rollups, narrowed by the page filters.

    severity: call has a finding of that severity. dimension: call failed that
    dimension. cluster_id: call has a member record in that cluster.
    outcome: pass = no failed record, fail = at least one.
    """
    calls = session.query(Call).join(Call.eval_records).distinct().order_by(Call.id).all()
    if cluster_id is not None:
        member_record_ids = {
            m.eval_record_id
            for m in session.query(ClusterMember).filter(ClusterMember.cluster_id == cluster_id)
        }
    avg_cost = _avg_judge_cost_cents(session)

    rows = []
    for call in calls:
        records = call.eval_records
        failed = {r.dimension for r in records if not r.passed}
        severities = {r.severity for r in records}
        if severity is not None and severity not in severities:
            continue
        if dimension is not None and dimension not in failed:
            continue
        if outcome == "pass" and failed:
            continue
        if outcome == "fail" and not failed:
            continue
        if cluster_id is not None and not any(r.id in member_record_ids for r in records):
            continue
        rows.append(
            ConversationRow(
                call_id=call.id,
                scenario=call.scenario,
                failed_dimensions=failed,
                has_p0="P0" in severities,
                avg_score=sum(r.score for r in records) / len(records),
                est_cost_cents=avg_cost,
                created_at=call.created_at,
                is_golden=call.is_golden,
            )
        )
    return rows


@dataclass(frozen=True)
class ClusterCard:
    """One cluster card on the Clusters page."""

    cluster_id: int
    label: str
    description: str
    routing: str
    severity: str
    size: int
    is_p0: bool


def cluster_cards(
    session: Session, routing: str | None = None, severity: str | None = None
) -> list[ClusterCard]:
    """Cluster cards, optionally filtered; sorted P0 > P1 > P2, then by size descending."""
    query = session.query(Cluster)
    if routing is not None:
        query = query.filter(Cluster.routing_suggestion == routing)
    if severity is not None:
        query = query.filter(Cluster.dominant_severity == severity)
    clusters = query.order_by(Cluster.size.desc()).all()
    cards = [
        ClusterCard(
            cluster_id=c.id,
            label=c.label,
            description=c.description,
            routing=c.routing_suggestion,
            severity=c.dominant_severity,
            size=c.size,
            is_p0=c.dominant_severity == "P0",
        )
        for c in clusters
    ]
    return sorted(cards, key=lambda c: (_severity_rank(c.severity), -c.size))


@dataclass(frozen=True)
class CallDetailData:
    """Everything the Call Detail page renders for one call."""

    call: Call
    records: list[EvalRecord]
    checks: list[DeterministicCheckResult]
    cluster: Cluster | None
    ground_truth: GroundTruthLabel | None


def call_detail(session: Session, call_id: str) -> CallDetailData | None:
    """Bundle one call's records (dimension order), checks, cluster, and ground truth."""
    call = session.get(Call, call_id)
    if call is None:
        return None
    records = sorted(
        call.eval_records,
        key=lambda r: (
            _DIMENSION_ORDER.index(r.dimension) if r.dimension in _DIMENSION_ORDER else 99
        ),
    )
    member = (
        session.query(ClusterMember)
        .filter(ClusterMember.eval_record_id.in_([r.id for r in records]))
        .first()
        if records
        else None
    )
    return CallDetailData(
        call=call,
        records=records,
        checks=sorted(call.check_results, key=lambda c: c.check_name),
        cluster=member.cluster if member else None,
        ground_truth=call.ground_truth,
    )


@dataclass(frozen=True)
class DimensionQuality:
    """Pass rate (0-1) for one dimension, with a 7-day-vs-prior-7-day delta."""

    pass_rate: float
    delta: float | None


def _as_utc(moment: datetime) -> datetime:
    """SQLite drops tzinfo on read; treat naive timestamps as UTC."""
    return moment if moment.tzinfo else moment.replace(tzinfo=UTC)


def quality_panel(session: Session) -> dict[str, DimensionQuality]:
    """Per-dimension pass rates plus week-over-week delta (None without prior data)."""
    records = session.query(EvalRecord).all()
    now = utcnow()
    week_ago, two_weeks_ago = now - timedelta(days=7), now - timedelta(days=14)

    def _rate(rows: list[EvalRecord]) -> float | None:
        return sum(r.passed for r in rows) / len(rows) if rows else None

    panel: dict[str, DimensionQuality] = {}
    for dim in _DIMENSION_ORDER:
        dim_records = [r for r in records if r.dimension == dim]
        rate = _rate(dim_records)
        if rate is None:
            panel[dim] = DimensionQuality(pass_rate=0.0, delta=None)
            continue
        recent = _rate([r for r in dim_records if _as_utc(r.created_at) >= week_ago])
        prior = _rate([r for r in dim_records if two_weeks_ago <= _as_utc(r.created_at) < week_ago])
        delta = recent - prior if recent is not None and prior is not None else None
        panel[dim] = DimensionQuality(pass_rate=rate, delta=delta)
    return panel


def severity_counts(session: Session) -> dict[str, int]:
    """Finding counts per severity across all eval records."""
    return {
        sev: session.query(EvalRecord).filter(EvalRecord.severity == sev).count()
        for sev in ("P0", "P1", "P2")
    }


@dataclass(frozen=True)
class FailureTrendPoint:
    """One day's failure rate, overall and per severity (fractions 0-1).

    The denominator is every EvalRecord created that day, not the call
    count: one call produces up to 4 dimension-level records (one per
    rubric dimension), so a call with several failing dimensions must not
    inflate the rate past 100%.
    """

    date: str
    overall_rate: float
    p0_rate: float
    p1_rate: float
    p2_rate: float
    total_records: int


def failure_trend(session: Session) -> list[FailureTrendPoint]:
    """Daily failure rate by severity, grouped by eval-run date (record created_at)."""
    records = session.query(EvalRecord).order_by(EvalRecord.created_at).all()
    by_date: dict[str, list[EvalRecord]] = {}
    for record in records:
        day = _as_utc(record.created_at).date().isoformat()
        by_date.setdefault(day, []).append(record)

    points = []
    for day in sorted(by_date):
        rows = by_date[day]
        total = len(rows)
        points.append(
            FailureTrendPoint(
                date=day,
                overall_rate=sum(not r.passed for r in rows) / total,
                p0_rate=sum(r.severity == "P0" for r in rows) / total,
                p1_rate=sum(r.severity == "P1" for r in rows) / total,
                p2_rate=sum(r.severity == "P2" for r in rows) / total,
                total_records=total,
            )
        )
    return points


@dataclass(frozen=True)
class CostTotals:
    """Cumulative judge cost and average per evaluated call (USD cents)."""

    total_eval_cents: float
    avg_per_call_cents: float


def cost_totals(session: Session) -> CostTotals:
    """Total judge spend to date and the per-evaluated-call average."""
    total = sum(
        row.cost_cents for row in session.query(LLMCallLog).filter(LLMCallLog.purpose == "judge")
    )
    n_calls = session.query(EvalRecord.call_id).distinct().count()
    return CostTotals(
        total_eval_cents=total,
        avg_per_call_cents=total / n_calls if n_calls else 0.0,
    )


def latest_fix(session: Session, cluster_id: int) -> FixProposal | None:
    """Most recent fix proposal for one cluster."""
    return (
        session.query(FixProposal)
        .filter(FixProposal.cluster_id == cluster_id)
        .order_by(FixProposal.id.desc())
        .first()
    )


def latest_regression(session: Session, fix_id: int) -> RegressionRun | None:
    """Most recent regression run for one fix."""
    return (
        session.query(RegressionRun)
        .filter(RegressionRun.fix_proposal_id == fix_id)
        .order_by(RegressionRun.id.desc())
        .first()
    )


def n_calls_for_scope(
    session: Session, scope: Literal["full", "unevaluated"], judge_model: str
) -> int:
    """Call count an eval run would visit, for the client-side cost estimate."""
    query = session.query(Call)
    if scope == "unevaluated":
        evaluated_ids = select(EvalRecord.call_id).where(
            EvalRecord.judge_model == judge_model,
            EvalRecord.prompt_version == PROMPT_VERSION,
        )
        query = query.filter(~Call.id.in_(evaluated_ids))
    return query.count()
