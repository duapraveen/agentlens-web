"""Dashboard query layer: plain ORM functions, no Streamlit imports.

All dashboard DB reads live here so they stay unit-testable and raw-SQL-free.
"""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from agentlens.models import Call, EvalRecord, JobRun
from agentlens.prompts.judge import PROMPT_VERSION


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
