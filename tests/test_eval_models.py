"""Tests for eval-side ORM models (AC-1.1, AC-1.3, AC-1.4)."""

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from agentlens.models import Call, DeterministicCheckResult, EvalRecord


def _call() -> Call:
    return Call(
        id="call_eval_1",
        scenario="symptom_triage",
        transcript=[{"speaker": "agent", "text": "hi"}],
        batch_id="b1",
    )


def _record(dimension: str = "safety_compliance") -> EvalRecord:
    return EvalRecord(
        call_id="call_eval_1",
        dimension=dimension,
        score=35,
        severity="P0",
        passed=False,
        failure_description="Missed escalation of chest pain.",
        judge_reasoning="Patient reported chest pain; agent continued booking.",
        pipeline_stage="reasoning",
        judge_model="claude-haiku-4-5",
        prompt_version="1.0",
        rubric_version="1.0",
        input_hash="abc123def4567890",
    )


def test_eval_record_roundtrip_and_relationship(db_session: Session) -> None:
    call = _call()
    db_session.add_all([call, _record()])
    db_session.commit()
    assert len(call.eval_records) == 1
    rec = call.eval_records[0]
    assert rec.severity == "P0"
    assert rec.passed is False
    assert rec.input_hash == "abc123def4567890"


def test_eval_record_idempotency_constraint(db_session: Session) -> None:
    db_session.add_all([_call(), _record(), _record()])
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_same_dimension_different_prompt_version_allowed(db_session: Session) -> None:
    other = _record()
    other.prompt_version = "1.1"
    db_session.add_all([_call(), _record(), other])
    db_session.commit()
    assert db_session.query(EvalRecord).count() == 2


def test_check_result_roundtrip_and_uniqueness(db_session: Session) -> None:
    call = _call()
    db_session.add_all(
        [
            call,
            DeterministicCheckResult(
                call_id="call_eval_1",
                check_name="missed_escalation",
                triggered=True,
                detail="red flag 'chest pain' with no escalation",
            ),
        ]
    )
    db_session.commit()
    assert call.check_results[0].triggered is True
    db_session.add(
        DeterministicCheckResult(
            call_id="call_eval_1", check_name="missed_escalation", triggered=False
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
