"""GET /api/conversations (list) and /api/conversations/{call_id} (detail)."""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from agentlens.api.deps import get_db
from agentlens.api.schemas import (
    CallDetailOut,
    CheckResultOut,
    ClusterLabelOut,
    ClusterRefOut,
    ConversationRowOut,
    ConversationsListOut,
    EvalRecordOut,
    GroundTruthOut,
)
from agentlens.dashboard.data import call_detail, conversation_rows
from agentlens.models import Cluster

router = APIRouter(tags=["conversations"])

_PAGE_SIZE = 25


@router.get("/conversations", response_model=ConversationsListOut)
def list_conversations(
    severity: str | None = Query(default=None),
    dimension: str | None = Query(default=None),
    cluster_id: int | None = Query(default=None),
    outcome: Literal["pass", "fail"] | None = Query(default=None),
    page: int = Query(default=0, ge=0),
    session: Session = Depends(get_db),  # noqa: B008
) -> ConversationsListOut:
    rows = conversation_rows(
        session, severity=severity, dimension=dimension, cluster_id=cluster_id, outcome=outcome
    )
    clusters = session.query(Cluster).order_by(Cluster.label).all()
    visible = rows[page * _PAGE_SIZE : (page + 1) * _PAGE_SIZE]
    return ConversationsListOut(
        rows=[ConversationRowOut.model_validate(r) for r in visible],
        total=len(rows),
        clusters=[ClusterLabelOut(id=c.id, label=c.label) for c in clusters],
    )


@router.get("/conversations/{call_id}", response_model=CallDetailOut)
def get_conversation(call_id: str, session: Session = Depends(get_db)) -> CallDetailOut:  # noqa: B008
    detail = call_detail(session, call_id)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"call {call_id!r} not found")
    return CallDetailOut(
        call_id=detail.call.id,
        scenario=detail.call.scenario,
        transcript=detail.call.transcript,
        records=[EvalRecordOut.model_validate(r) for r in detail.records],
        checks=[CheckResultOut.model_validate(c) for c in detail.checks],
        cluster=ClusterRefOut(id=detail.cluster.id, label=detail.cluster.label)
        if detail.cluster is not None
        else None,
        ground_truth=GroundTruthOut.model_validate(detail.ground_truth)
        if detail.ground_truth is not None
        else None,
    )
