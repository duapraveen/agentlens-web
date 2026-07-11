"""Tests for the dashboard query layer (no Streamlit involved)."""

from sqlalchemy.orm import Session

from agentlens.dashboard.data import status_summary
from agentlens.models import Call, JobRun, utcnow


def test_status_summary_counts_and_last_eval(db_session: Session) -> None:
    for i in range(3):
        db_session.add(
            Call(
                id=f"call_{i}",
                scenario="symptom_triage",
                transcript=[{"speaker": "agent", "text": "hi"}],
                batch_id="b1",
                is_golden=i == 0,
            )
        )
    run = JobRun(job_name="run_evals", status="completed", finished_at=utcnow())
    db_session.add(run)
    db_session.commit()

    summary = status_summary(db_session)
    assert summary.n_calls == 3
    assert summary.n_golden == 1
    assert summary.last_eval_at is not None


def test_status_summary_empty_db(db_session: Session) -> None:
    summary = status_summary(db_session)
    assert (summary.n_calls, summary.n_golden, summary.last_eval_at) == (0, 0, None)
