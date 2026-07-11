"""Tests for golden-set cluster purity (AC-2.3)."""

from sqlalchemy.orm import Session

from agentlens.clustering.purity import compute_mode_purity
from agentlens.models import Call, Cluster, ClusterMember, EvalRecord, GroundTruthLabel


def _failure_call(
    session: Session,
    call_id: str,
    mode: str,
    dimension: str,
    cluster: Cluster | None,
) -> None:
    session.add(
        Call(
            id=call_id,
            scenario="symptom_triage",
            transcript=[{"speaker": "agent", "text": "hi"}],
            batch_id="b1",
            is_golden=True,
        )
    )
    session.add(
        GroundTruthLabel(
            call_id=call_id, failure_mode=mode, pipeline_stage="reasoning", severity="P1"
        )
    )
    record = EvalRecord(
        call_id=call_id,
        dimension=dimension,
        score=30,
        severity="P1",
        passed=False,
        failure_description="d",
        judge_reasoning="r",
        judge_model="claude-haiku-4-5",
        prompt_version="1.0",
        rubric_version="1.0",
        input_hash="h",
    )
    session.add(record)
    session.flush()
    if cluster is not None:
        session.add(ClusterMember(cluster_id=cluster.id, eval_record_id=record.id))


def test_mode_purity(db_session: Session) -> None:
    a = Cluster(
        label="a", description="", routing_suggestion="prompt_fix", dominant_severity="P1", size=0
    )
    b = Cluster(
        label="b", description="", routing_suggestion="prompt_fix", dominant_severity="P1", size=0
    )
    db_session.add_all([a, b])
    db_session.flush()
    # pure mode: 3/3 members in cluster a
    for i in range(3):
        _failure_call(db_session, f"call_pure_{i}", "dead_end_loop", "task_completion", a)
    # split mode: 1 in a, 1 in b
    _failure_call(db_session, "call_split_0", "wrong_retrieval", "factual_accuracy", a)
    _failure_call(db_session, "call_split_1", "wrong_retrieval", "factual_accuracy", b)
    # unclustered mode: record exists but never clustered
    _failure_call(db_session, "call_none_0", "missed_escalation", "safety_compliance", None)
    db_session.commit()

    purity = compute_mode_purity(db_session)
    assert purity["dead_end_loop"] == 1.0
    assert purity["wrong_retrieval"] == 0.5
    assert purity["missed_escalation"] == 0.0


def test_dimension_matched_record_preferred(db_session: Session) -> None:
    """When a call has multiple failed records, the mode's expected dimension wins."""
    a = Cluster(
        label="a", description="", routing_suggestion="prompt_fix", dominant_severity="P1", size=0
    )
    b = Cluster(
        label="b", description="", routing_suggestion="prompt_fix", dominant_severity="P1", size=0
    )
    db_session.add_all([a, b])
    db_session.flush()
    # dead_end_loop expects task_completion; put that record in cluster a
    _failure_call(db_session, "call_multi", "dead_end_loop", "task_completion", a)
    # same call also failed communication_quality, clustered elsewhere
    extra = EvalRecord(
        call_id="call_multi",
        dimension="communication_quality",
        score=50,
        severity="P2",
        passed=False,
        failure_description="verbose",
        judge_reasoning="r",
        judge_model="claude-haiku-4-5",
        prompt_version="1.0",
        rubric_version="1.0",
        input_hash="h",
    )
    db_session.add(extra)
    db_session.flush()
    db_session.add(ClusterMember(cluster_id=b.id, eval_record_id=extra.id))
    db_session.commit()

    purity = compute_mode_purity(db_session)
    assert purity["dead_end_loop"] == 1.0  # judged by the task_completion record in a
