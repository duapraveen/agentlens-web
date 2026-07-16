"""Tests for the reviewer queue and verdict submission (AC-4.1)."""

from sqlalchemy.orm import Session

from agentlens.feedback.queue import next_call_id_for_review, review_queue, submit_review
from agentlens.models import Call, EvalRecord, Review


def _finding(session: Session, call_id: str, severity: str, passed: bool = False) -> EvalRecord:
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
        score=20 if not passed else 95,
        severity=severity,
        passed=passed,
        failure_description=None if passed else "issue",
        judge_reasoning="r",
        judge_model="claude-haiku-4-5",
        prompt_version="1.0",
        rubric_version="1.0",
        input_hash="h",
    )
    session.add(record)
    session.flush()
    return record


def test_queue_orders_unreviewed_first_then_severity(db_session: Session) -> None:
    p1 = _finding(db_session, "call_p1", "P1")
    p0_reviewed = _finding(db_session, "call_p0r", "P0")
    p0 = _finding(db_session, "call_p0", "P0")
    p2 = _finding(db_session, "call_p2", "P2")
    _finding(db_session, "call_clean", "none", passed=True)  # never queued
    db_session.add(Review(eval_record_id=p0_reviewed.id, verdict="agree"))
    db_session.commit()

    queue = review_queue(db_session)
    assert [r.id for r in queue] == [p0.id, p1.id, p2.id, p0_reviewed.id]


def test_next_call_id_for_review_follows_queue_order(db_session: Session) -> None:
    p1 = _finding(db_session, "call_p1", "P1")
    p0_reviewed = _finding(db_session, "call_p0r", "P0")
    _finding(db_session, "call_p0", "P0")
    db_session.add(Review(eval_record_id=p0_reviewed.id, verdict="agree"))
    db_session.commit()

    assert next_call_id_for_review(db_session) == "call_p0"

    # once call_p0's finding is reviewed, the next unreviewed call is call_p1
    p0 = db_session.query(EvalRecord).filter_by(call_id="call_p0").one()
    submit_review(db_session, p0.id, "agree")
    db_session.commit()
    assert next_call_id_for_review(db_session) == p1.call_id


def test_next_call_id_for_review_none_when_queue_empty(db_session: Session) -> None:
    assert next_call_id_for_review(db_session) is None


def test_submit_review_creates_then_updates(db_session: Session) -> None:
    record = _finding(db_session, "call_s", "P1")
    first = submit_review(db_session, record.id, "agree", note="looks right")
    db_session.commit()
    second = submit_review(db_session, record.id, "disagree", note="on reflection, no")
    db_session.commit()

    assert first.id == second.id
    reviews = db_session.query(Review).all()
    assert len(reviews) == 1
    assert reviews[0].verdict == "disagree"
    assert reviews[0].note == "on reflection, no"
