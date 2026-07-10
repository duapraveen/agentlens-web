"""Tests for judge quality metrics vs golden ground truth (spec §2, T206)."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from agentlens.evals.metrics import compute_judge_quality
from agentlens.jobs.judge_metrics import main as metrics_main
from agentlens.models import (
    Base,
    Call,
    DeterministicCheckResult,
    EvalRecord,
    GroundTruthLabel,
    JobRun,
)

_DIMS = ["task_completion", "factual_accuracy", "safety_compliance", "communication_quality"]


def _call(session: Session, call_id: str, *, golden: bool = True) -> None:
    session.add(
        Call(
            id=call_id,
            scenario="symptom_triage",
            transcript=[{"speaker": "agent", "text": "hi"}],
            batch_id="b1",
            is_golden=golden,
        )
    )


def _label(session: Session, call_id: str, mode: str, severity: str) -> None:
    session.add(
        GroundTruthLabel(
            call_id=call_id, failure_mode=mode, pipeline_stage="reasoning", severity=severity
        )
    )


def _evals(session: Session, call_id: str, *, flagged: str | None) -> None:
    """Four eval records; if flagged, safety_compliance gets that severity."""
    for dim in _DIMS:
        severity = flagged if (flagged and dim == "safety_compliance") else "none"
        session.add(
            EvalRecord(
                call_id=call_id,
                dimension=dim,
                score=30 if severity != "none" else 90,
                severity=severity,
                passed=severity == "none",
                judge_reasoning="r",
                judge_model="claude-haiku-4-5",
                prompt_version="1.0",
                rubric_version="1.0",
                input_hash="hash000000000000",
            )
        )


def _seed(session: Session) -> None:
    # TP: labeled P0 failure, judge flags P0
    _call(session, "call_tp")
    _label(session, "call_tp", "missed_escalation", "P0")
    _evals(session, "call_tp", flagged="P0")
    # FN: labeled P1 failure, judge clean — but deterministic check triggered
    _call(session, "call_fn")
    _label(session, "call_fn", "dead_end_loop", "P1")
    _evals(session, "call_fn", flagged=None)
    session.add(
        DeterministicCheckResult(
            call_id="call_fn", check_name="missed_escalation", triggered=True, detail="d"
        )
    )
    # FP: clean call, judge flags P1
    _call(session, "call_fp")
    _evals(session, "call_fp", flagged="P1")
    # TN: clean call, judge clean
    _call(session, "call_tn")
    _evals(session, "call_tn", flagged=None)
    # missing: golden call without eval records
    _call(session, "call_missing")
    # non-golden call must be ignored entirely
    _call(session, "call_nongolden", golden=False)
    _evals(session, "call_nongolden", flagged="P0")
    session.commit()


def test_confusion_matrix_and_rates(db_session: Session) -> None:
    _seed(db_session)
    q = compute_judge_quality(db_session, "claude-haiku-4-5", "1.0")
    assert (q.n_golden, q.n_missing) == (5, 1)
    assert (q.tp, q.fp, q.fn, q.tn) == (1, 1, 1, 1)
    assert q.precision == pytest.approx(0.5)
    assert q.recall == pytest.approx(0.5)


def test_p0_subset(db_session: Session) -> None:
    _seed(db_session)
    q = compute_judge_quality(db_session, "claude-haiku-4-5", "1.0")
    # actual P0: call_tp; predicted P0: call_tp only (call_fp was P1)
    assert q.p0_precision == pytest.approx(1.0)
    assert q.p0_recall == pytest.approx(1.0)


def test_combined_includes_deterministic_triggers(db_session: Session) -> None:
    _seed(db_session)
    q = compute_judge_quality(db_session, "claude-haiku-4-5", "1.0")
    # deterministic trigger on call_fn converts the FN into a combined TP
    assert q.combined_recall == pytest.approx(1.0)
    assert q.combined_precision == pytest.approx(2 / 3)


def test_per_mode_recall(db_session: Session) -> None:
    _seed(db_session)
    q = compute_judge_quality(db_session, "claude-haiku-4-5", "1.0")
    assert q.per_mode_recall == {"missed_escalation": 1.0, "dead_end_loop": 0.0}


def test_zero_division_yields_zero(db_session: Session) -> None:
    _call(db_session, "call_only_tn")
    _evals(db_session, "call_only_tn", flagged=None)
    db_session.commit()
    q = compute_judge_quality(db_session, "claude-haiku-4-5", "1.0")
    assert q.precision == 0.0 and q.recall == 0.0


@pytest.fixture()
def metrics_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    url = f"sqlite:///{tmp_path}/metrics.db"
    monkeypatch.setenv("AGENTLENS_DATABASE_URL", url)
    monkeypatch.setenv("AGENTLENS_JOBS_LOG_PATH", str(tmp_path / "logs" / "jobs.log"))
    engine = create_engine(url)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        _seed(session)
    yield url


def test_metrics_job_stores_baseline(metrics_env: str) -> None:
    assert metrics_main([]) == 0
    engine = create_engine(metrics_env)
    with Session(engine) as session:
        run = session.query(JobRun).filter_by(job_name="judge_metrics").one()
        assert run.status == "completed"
        assert run.summary["precision"] == pytest.approx(0.5)
        assert run.summary["judge_model"] == "claude-haiku-4-5"
