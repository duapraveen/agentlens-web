"""Tests for cluster ORM models."""

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from agentlens.models import Call, Cluster, ClusterMember, EvalRecord


def _seed(session: Session) -> EvalRecord:
    session.add(
        Call(
            id="call_c1",
            scenario="symptom_triage",
            transcript=[{"speaker": "agent", "text": "hi"}],
            batch_id="b1",
        )
    )
    record = EvalRecord(
        call_id="call_c1",
        dimension="factual_accuracy",
        score=40,
        severity="P1",
        passed=False,
        failure_description="Agent invented an appointment slot.",
        judge_reasoning="r",
        judge_model="claude-haiku-4-5",
        prompt_version="1.0",
        rubric_version="1.0",
        input_hash="h",
    )
    session.add(record)
    session.commit()
    return record


def test_cluster_roundtrip_with_members(db_session: Session) -> None:
    record = _seed(db_session)
    cluster = Cluster(
        label="hallucinated availability",
        description="Agent invents slots.",
        routing_suggestion="prompt_fix",
        dominant_severity="P1",
        size=1,
    )
    db_session.add(cluster)
    db_session.flush()
    db_session.add(ClusterMember(cluster_id=cluster.id, eval_record_id=record.id))
    db_session.commit()
    assert len(cluster.members) == 1
    assert cluster.members[0].eval_record.failure_description is not None


def test_eval_record_belongs_to_one_cluster(db_session: Session) -> None:
    record = _seed(db_session)
    a = Cluster(
        label="a", description="", routing_suggestion="prompt_fix", dominant_severity="P1", size=1
    )
    b = Cluster(
        label="b", description="", routing_suggestion="ops_process", dominant_severity="P1", size=1
    )
    db_session.add_all([a, b])
    db_session.flush()
    db_session.add(ClusterMember(cluster_id=a.id, eval_record_id=record.id))
    db_session.add(ClusterMember(cluster_id=b.id, eval_record_id=record.id))
    with pytest.raises(IntegrityError):
        db_session.commit()
