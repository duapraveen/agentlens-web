"""GET /api/status and /api/overview — sidebar status block and landing page."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from agentlens.api.deps import get_db
from agentlens.api.schemas import OverviewOut, StatusSummaryOut
from agentlens.dashboard.data import (
    cluster_cards,
    cost_totals,
    failure_trend,
    last_job_run,
    quality_panel,
    severity_counts,
    status_summary,
)
from agentlens.feedback.calibration import compute_agreement

router = APIRouter(tags=["overview"])


@router.get("/status", response_model=StatusSummaryOut)
def get_status(session: Session = Depends(get_db)) -> StatusSummaryOut:  # noqa: B008
    return StatusSummaryOut.model_validate(status_summary(session))


@router.get("/overview", response_model=OverviewOut)
def get_overview(session: Session = Depends(get_db)) -> OverviewOut:  # noqa: B008
    quality = quality_panel(session)
    severities = severity_counts(session)
    agreement = compute_agreement(session)
    metrics_run = last_job_run(session, "judge_metrics")
    top = cluster_cards(session)[:5]
    costs = cost_totals(session)
    summary = metrics_run.summary if metrics_run else {}
    return OverviewOut.model_validate(
        {
            "quality": quality,
            "severities": severities,
            "precision": summary.get("precision"),
            "recall": summary.get("recall"),
            "agreement": agreement.agreement if agreement.n_reviews else None,
            "n_reviews": agreement.n_reviews,
            "top_clusters": top,
            "total_eval_cents": costs.total_eval_cents,
            "avg_per_call_cents": costs.avg_per_call_cents,
            "failure_trend": failure_trend(session),
        }
    )
