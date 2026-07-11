"""Dashboard query layer: plain ORM functions, no Streamlit imports.

All dashboard DB reads live here so they stay unit-testable and raw-SQL-free.
"""

from dataclasses import dataclass
from datetime import datetime
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
    GroundTruthLabel,
    JobRun,
    LLMCallLog,
)
from agentlens.prompts.judge import PROMPT_VERSION

_DIMENSION_ORDER = [d.value for d in Dimension]


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
            )
        )
    return rows


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
