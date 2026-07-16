"""GET /api/review-queue and POST /api/review-queue/{eval_record_id} — human calibration.

The queue operates at the call level: when a call has an unreviewed failing
finding, the reviewer sees all of that call's dimension scores (not just the
failing one), each with its own submittable verdict (docs/superpowers/specs/
2026-07-15-review-queue-per-score-review.md).
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from agentlens.api.deps import get_db
from agentlens.api.schemas import (
    AgreementStatsOut,
    CallReviewOut,
    CheckResultOut,
    ReviewQueueOut,
    ScoredRecordOut,
    SubmitReviewIn,
)
from agentlens.dashboard.data import call_detail
from agentlens.feedback.calibration import compute_agreement
from agentlens.feedback.queue import next_call_id_for_review, review_queue, submit_review

router = APIRouter(tags=["review-queue"])


def _current_queue(session: Session) -> ReviewQueueOut:
    stats = compute_agreement(session)
    pending = [r for r in review_queue(session) if r.review is None]
    current = None
    call_id = next_call_id_for_review(session)
    if call_id is not None:
        detail = call_detail(session, call_id)
        assert detail is not None  # call_id came from a query over existing records
        current = CallReviewOut(
            call_id=detail.call.id,
            scenario=detail.call.scenario,
            transcript=detail.call.transcript,
            records=[ScoredRecordOut.model_validate(r) for r in detail.records],
            checks=[CheckResultOut.model_validate(c) for c in detail.checks],
        )
    return ReviewQueueOut(
        stats=AgreementStatsOut.model_validate(stats),
        pending_count=len(pending),
        current=current,
    )


@router.get("/review-queue", response_model=ReviewQueueOut)
def get_review_queue(session: Session = Depends(get_db)) -> ReviewQueueOut:  # noqa: B008
    return _current_queue(session)


@router.post("/review-queue/{eval_record_id}", response_model=ReviewQueueOut)
def post_review(
    eval_record_id: int,
    body: SubmitReviewIn,
    session: Session = Depends(get_db),  # noqa: B008
) -> ReviewQueueOut:
    if body.verdict not in ("agree", "disagree"):
        raise HTTPException(status_code=400, detail="verdict must be 'agree' or 'disagree'")
    submit_review(session, eval_record_id, body.verdict, body.note)  # type: ignore[arg-type]
    session.commit()
    return _current_queue(session)
