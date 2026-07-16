"""Reviewer queue and verdict submission (AC-4.1)."""

from typing import Literal

from sqlalchemy import case
from sqlalchemy.orm import Session

from agentlens.models import EvalRecord, Review

_SEVERITY_RANK = case(
    (EvalRecord.severity == "P0", 0),
    (EvalRecord.severity == "P1", 1),
    (EvalRecord.severity == "P2", 2),
    else_=3,
)


def review_queue(session: Session) -> list[EvalRecord]:
    """Failed findings for review: unreviewed first, then P0 > P1 > P2, then id."""
    return (
        session.query(EvalRecord)
        .outerjoin(Review)
        .filter(~EvalRecord.passed)
        .order_by(Review.id.is_not(None), _SEVERITY_RANK, EvalRecord.id)
        .all()
    )


def next_call_id_for_review(session: Session) -> str | None:
    """Call id of the next call with an unreviewed failed finding, by queue order."""
    for record in review_queue(session):
        if record.review is None:
            return record.call_id
    return None


def submit_review(
    session: Session,
    eval_record_id: int,
    verdict: Literal["agree", "disagree"],
    note: str | None = None,
) -> Review:
    """Record the human verdict on one finding; resubmission updates in place. Caller commits."""
    review = session.query(Review).filter(Review.eval_record_id == eval_record_id).one_or_none()
    if review is None:
        review = Review(eval_record_id=eval_record_id, verdict=verdict, note=note)
        session.add(review)
    else:
        review.verdict = verdict
        review.note = note
    session.flush()
    return review
