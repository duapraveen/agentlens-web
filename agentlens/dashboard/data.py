"""Dashboard query layer: plain ORM functions, no Streamlit imports.

All dashboard DB reads live here so they stay unit-testable and raw-SQL-free.
"""

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from agentlens.models import Call, JobRun


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
