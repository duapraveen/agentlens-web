"""GET /api/clusters — recurring failure patterns."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from agentlens.api.deps import get_db
from agentlens.api.schemas import ClusterCardOut, ClustersListOut
from agentlens.dashboard.data import cluster_cards, last_job_run

router = APIRouter(tags=["clusters"])


@router.get("/clusters", response_model=ClustersListOut)
def list_clusters(
    routing: str | None = Query(default=None),
    severity: str | None = Query(default=None),
    focus_id: int | None = Query(default=None),
    session: Session = Depends(get_db),  # noqa: B008
) -> ClustersListOut:
    cards = cluster_cards(session, routing=routing, severity=severity)
    if focus_id is not None:
        cards = [c for c in cards if c.cluster_id == focus_id]
    last_run = last_job_run(session, "recluster")
    return ClustersListOut(
        cards=[ClusterCardOut.model_validate(c) for c in cards],
        n_failures=sum(c.size for c in cards),
        last_clustered_at=last_run.finished_at if last_run else None,
    )
