"""Tests for judge version comparison and the regression gate (AC-4.3)."""

from sqlalchemy.orm import Session

from agentlens.feedback.compare import compare_judge_versions
from agentlens.models import Call, EvalRecord, GroundTruthLabel, Review

_MODEL = "claude-haiku-4-5"


def _golden_call(session: Session, call_id: str, injected: bool) -> None:
    session.add(
        Call(
            id=call_id,
            scenario="symptom_triage",
            transcript=[{"speaker": "agent", "text": "hi"}],
            batch_id="b1",
            is_golden=True,
        )
    )
    if injected:
        session.add(
            GroundTruthLabel(
                call_id=call_id,
                failure_mode="dead_end_loop",
                pipeline_stage="orchestration",
                severity="P1",
            )
        )


def _judged(
    session: Session,
    call_id: str,
    prompt_version: str,
    flagged: bool,
    verdict: str | None = None,
) -> None:
    record = EvalRecord(
        call_id=call_id,
        dimension="task_completion",
        score=30 if flagged else 95,
        severity="P1" if flagged else "none",
        passed=not flagged,
        failure_description="issue" if flagged else None,
        judge_reasoning="r",
        judge_model=_MODEL,
        prompt_version=prompt_version,
        rubric_version=prompt_version,
        input_hash="h",
    )
    session.add(record)
    session.flush()
    if verdict is not None:
        session.add(Review(eval_record_id=record.id, verdict=verdict))


def _seed_two_versions(session: Session, candidate_worse: bool) -> None:
    """4 golden calls (2 injected). Baseline v1.0 is perfect; candidate v1.1 varies."""
    for call_id, injected in (("g1", True), ("g2", True), ("g3", False), ("g4", False)):
        _golden_call(session, call_id, injected)
    for call_id in ("g1", "g2", "g3", "g4"):
        _judged(session, call_id, "1.0", flagged=call_id in ("g1", "g2"), verdict="agree")
    candidate_flags = ("g1", "g3") if candidate_worse else ("g1", "g2")
    for call_id in ("g1", "g2", "g3", "g4"):
        _judged(session, call_id, "1.1", flagged=call_id in candidate_flags, verdict="disagree")
    session.commit()


def test_regressing_candidate_is_flagged(db_session: Session) -> None:
    _seed_two_versions(db_session, candidate_worse=True)
    result = compare_judge_versions(db_session, _MODEL, "1.0", "1.1")

    assert (result.baseline.precision, result.baseline.recall) == (1.0, 1.0)
    assert (result.candidate.precision, result.candidate.recall) == (0.5, 0.5)
    assert result.precision_delta == -0.5
    assert result.recall_delta == -0.5
    assert result.regression_flagged is True
    assert result.baseline_agreement.n_reviews == 4
    assert result.baseline_agreement.agreement == 1.0
    assert result.candidate_agreement.agreement == 0.0


def test_equal_candidate_passes(db_session: Session) -> None:
    _seed_two_versions(db_session, candidate_worse=False)
    result = compare_judge_versions(db_session, _MODEL, "1.0", "1.1")
    assert result.precision_delta == 0.0
    assert result.recall_delta == 0.0
    assert result.regression_flagged is False
