"""Tests for the dashboard query layer (no Streamlit involved)."""

from pathlib import Path

from sqlalchemy.orm import Session

from agentlens.dashboard.data import (
    last_job_run,
    n_calls_for_scope,
    status_summary,
    tail_log,
)
from agentlens.models import Call, EvalRecord, JobRun, utcnow


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


def test_last_job_run_picks_latest_of_name(db_session: Session) -> None:
    old = JobRun(job_name="recluster", status="completed", finished_at=utcnow())
    new = JobRun(job_name="recluster", status="completed", finished_at=utcnow())
    other = JobRun(job_name="run_evals", status="completed", finished_at=utcnow())
    db_session.add_all([old, new, other])
    db_session.commit()

    found = last_job_run(db_session, "recluster")
    assert found is not None and found.id == new.id
    assert last_job_run(db_session, "generate_corpus") is None


def test_tail_log(tmp_path: Path) -> None:
    log = tmp_path / "jobs.log"
    log.write_text("\n".join(f"line {i}" for i in range(30)) + "\n")
    assert tail_log(log, n=3) == ["line 27", "line 28", "line 29"]
    assert tail_log(tmp_path / "missing.log", n=3) == []


def test_n_calls_for_scope(db_session: Session) -> None:
    for i in range(3):
        db_session.add(
            Call(
                id=f"call_{i}",
                scenario="symptom_triage",
                transcript=[{"speaker": "agent", "text": "hi"}],
                batch_id="b1",
            )
        )
    db_session.add(
        EvalRecord(
            call_id="call_0",
            dimension="task_completion",
            score=90,
            severity="none",
            passed=True,
            judge_reasoning="r",
            judge_model="claude-haiku-4-5",
            prompt_version="1.0",
            rubric_version="1.0",
            input_hash="h",
        )
    )
    db_session.commit()

    assert n_calls_for_scope(db_session, "full", "claude-haiku-4-5") == 3
    assert n_calls_for_scope(db_session, "unevaluated", "claude-haiku-4-5") == 2
