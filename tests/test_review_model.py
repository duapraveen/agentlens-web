"""Tests for the Review model (AC-4.1): one human verdict per judge finding."""

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from agentlens.models import Call, EvalRecord, Review


def _finding(session: Session, call_id: str = "call_r1") -> EvalRecord:
    session.add(
        Call(
            id=call_id,
            scenario="symptom_triage",
            transcript=[{"speaker": "agent", "text": "hi"}],
            batch_id="b1",
        )
    )
    record = EvalRecord(
        call_id=call_id,
        dimension="safety_compliance",
        score=20,
        severity="P0",
        passed=False,
        failure_description="missed escalation",
        judge_reasoning="r",
        judge_model="claude-haiku-4-5",
        prompt_version="1.0",
        rubric_version="1.0",
        input_hash="h",
    )
    session.add(record)
    session.flush()
    return record


def test_review_roundtrip(db_session: Session) -> None:
    record = _finding(db_session)
    db_session.add(Review(eval_record_id=record.id, verdict="agree", note="confirmed"))
    db_session.commit()

    loaded = db_session.query(Review).one()
    assert loaded.verdict == "agree"
    assert loaded.note == "confirmed"
    assert loaded.created_at is not None
    assert record.review is loaded


def test_one_review_per_finding(db_session: Session) -> None:
    record = _finding(db_session)
    db_session.add(Review(eval_record_id=record.id, verdict="agree"))
    db_session.commit()
    db_session.add(Review(eval_record_id=record.id, verdict="disagree"))
    with pytest.raises(IntegrityError):
        db_session.commit()
