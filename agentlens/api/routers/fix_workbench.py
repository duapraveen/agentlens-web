"""Fix Workbench endpoints: propose a fix, apply it, run regression."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from agentlens.api.deps import get_db
from agentlens.api.schemas import (
    ClusterCardOut,
    ClusterLabelOut,
    FixProposalOut,
    FixWorkbenchOut,
    RegressionRunOut,
)
from agentlens.dashboard.data import cluster_cards, latest_fix, latest_regression
from agentlens.evals.runner import evaluate_call
from agentlens.fixes.propose import propose_fix
from agentlens.fixes.regression import regenerate_for_fix
from agentlens.fixes.report import build_regression_run
from agentlens.models import Cluster, FixProposal

router = APIRouter(tags=["fix-workbench"])


@router.get("/fix-workbench/clusters", response_model=list[ClusterLabelOut])
def list_selectable_clusters(session: Session = Depends(get_db)) -> list[ClusterLabelOut]:  # noqa: B008
    return [
        ClusterLabelOut(id=c.cluster_id, label=c.label)
        for c in cluster_cards(session)
        if not c.is_p0
    ]


def _get_cluster(session: Session, cluster_id: int) -> Cluster:
    cluster = session.get(Cluster, cluster_id)
    if cluster is None:
        raise HTTPException(status_code=404, detail=f"cluster {cluster_id} not found")
    return cluster


@router.get("/fix-workbench/{cluster_id}", response_model=FixWorkbenchOut)
def get_fix_workbench(
    cluster_id: int,
    session: Session = Depends(get_db),  # noqa: B008
) -> FixWorkbenchOut:
    _get_cluster(session, cluster_id)
    fix = latest_fix(session, cluster_id)
    regression = latest_regression(session, fix.id) if fix is not None else None
    card = next(c for c in cluster_cards(session) if c.cluster_id == cluster_id)
    return FixWorkbenchOut(
        cluster=ClusterCardOut.model_validate(card),
        fix=FixProposalOut.model_validate(fix) if fix is not None else None,
        regression=RegressionRunOut.model_validate(regression) if regression is not None else None,
    )


@router.post("/fix-workbench/{cluster_id}/generate", response_model=FixProposalOut)
def generate_fix(
    cluster_id: int,
    session: Session = Depends(get_db),  # noqa: B008
) -> FixProposalOut:
    cluster = _get_cluster(session, cluster_id)
    result = propose_fix(session, cluster)
    if not result.success or result.parsed is None:
        raise HTTPException(status_code=422, detail=f"fix generation failed: {result.error}")
    fix = FixProposal(
        cluster_id=cluster.id,
        fix_type=result.parsed.fix_type,
        rationale=result.parsed.rationale,
        patch=result.parsed.patch,
    )
    session.add(fix)
    session.commit()
    return FixProposalOut.model_validate(fix)


@router.post("/fix-workbench/{cluster_id}/apply-regression", response_model=RegressionRunOut)
def apply_regression(
    cluster_id: int,
    session: Session = Depends(get_db),  # noqa: B008
) -> RegressionRunOut:
    cluster = _get_cluster(session, cluster_id)
    if cluster.dominant_severity == "P0":
        raise HTTPException(
            status_code=400,
            detail="P0 findings require human acknowledgment before regression can run",
        )
    fix = latest_fix(session, cluster_id)
    if fix is None:
        raise HTTPException(status_code=400, detail="no fix proposed yet for this cluster")
    regenerated = regenerate_for_fix(session, fix)
    for call in regenerated:
        evaluate_call(session, call)
    run = build_regression_run(session, fix, regenerated)
    session.commit()
    return RegressionRunOut.model_validate(run)
