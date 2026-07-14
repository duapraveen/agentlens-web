"""GET /api/review-queue and POST /api/review-queue/{eval_record_id} — human calibration."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from agentlens.api.deps import get_db
from agentlens.api.schemas import (
    AgreementStatsOut,
    CheckResultOut,
    FindingOut,
    ReviewQueueOut,
    SubmitReviewIn,
)
from agentlens.feedback.calibration import compute_agreement
from agentlens.feedback.queue import review_queue, submit_review

router = APIRouter(tags=["review-queue"])


def _current_queue(session: Session) -> ReviewQueueOut:
    stats = compute_agreement(session)
    queue = review_queue(session)
    pending = [r for r in queue if r.review is None]
    current = None
    if pending:
        finding = pending[0]
        current = FindingOut(
            eval_record_id=finding.id,
            call_id=finding.call.id,
            scenario=finding.call.scenario,
            dimension=finding.dimension,
            score=finding.score,
            severity=finding.severity,
            failure_description=finding.failure_description,
            checks=[CheckResultOut.model_validate(c) for c in finding.call.check_results],
            transcript=finding.call.transcript,
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
    eval_record_id: int, body: SubmitReviewIn, session: Session = Depends(get_db)  # noqa: B008
) -> ReviewQueueOut:
    if body.verdict not in ("agree", "disagree"):
        raise HTTPException(status_code=400, detail="verdict must be 'agree' or 'disagree'")
    submit_review(session, eval_record_id, body.verdict, body.note)  # type: ignore[arg-type]
    session.commit()
    return _current_queue(session)
