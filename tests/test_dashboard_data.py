"""Tests for the dashboard query layer (no Streamlit involved)."""

from pathlib import Path

from sqlalchemy.orm import Session

from agentlens.dashboard.data import (
    call_detail,
    conversation_rows,
    last_job_run,
    n_calls_for_scope,
    status_summary,
    tail_log,
)
from agentlens.models import Call, Cluster, ClusterMember, EvalRecord, JobRun, utcnow


def test_status_summary_counts_and_last_eval(db_session: Session) -> None:
    for i in range(3):
        db_session.add(
            Call(
                id=f"call_{i}",
                scenario="symptom_triage",
                transcript=[{"speaker": "agent", "text": "hi"}],
                batch_id="b1",
                is_golden=i == 0,
            )
        )
    run = JobRun(job_name="run_evals", status="completed", finished_at=utcnow())
    db_session.add(run)
    db_session.commit()

    summary = status_summary(db_session)
    assert summary.n_calls == 3
    assert summary.n_golden == 1
    assert summary.last_eval_at is not None


def test_status_summary_empty_db(db_session: Session) -> None:
    summary = status_summary(db_session)
    assert (summary.n_calls, summary.n_golden, summary.last_eval_at) == (0, 0, None)


def test_last_job_run_picks_latest_of_name(db_session: Session) -> None:
    old = JobRun(job_name="recluster", status="completed", finished_at=utcnow())
    new = JobRun(job_name="recluster", status="completed", finished_at=utcnow())
    other = JobRun(job_name="run_evals", status="completed", finished_at=utcnow())
    db_session.add_all([old, new, other])
    db_session.commit()

    found = last_job_run(db_session, "recluster")
    assert found is not None and found.id == new.id
    assert last_job_run(db_session, "generate_corpus") is None


def test_tail_log(tmp_path: Path) -> None:
    log = tmp_path / "jobs.log"
    log.write_text("\n".join(f"line {i}" for i in range(30)) + "\n")
    assert tail_log(log, n=3) == ["line 27", "line 28", "line 29"]
    assert tail_log(tmp_path / "missing.log", n=3) == []


def test_n_calls_for_scope(db_session: Session) -> None:
    for i in range(3):
        db_session.add(
            Call(
                id=f"call_{i}",
                scenario="symptom_triage",
                transcript=[{"speaker": "agent", "text": "hi"}],
                batch_id="b1",
            )
        )
    db_session.add(
        EvalRecord(
            call_id="call_0",
            dimension="task_completion",
            score=90,
            severity="none",
            passed=True,
            judge_reasoning="r",
            judge_model="claude-haiku-4-5",
            prompt_version="1.0",
            rubric_version="1.0",
            input_hash="h",
        )
    )
    db_session.commit()

    assert n_calls_for_scope(db_session, "full", "claude-haiku-4-5") == 3
    assert n_calls_for_scope(db_session, "unevaluated", "claude-haiku-4-5") == 2


def _record(call_id: str, dim: str, severity: str, score: int) -> EvalRecord:
    return EvalRecord(
        call_id=call_id,
        dimension=dim,
        score=score,
        severity=severity,
        passed=severity == "none",
        failure_description=None if severity == "none" else "issue",
        judge_reasoning="r",
        judge_model="claude-haiku-4-5",
        prompt_version="1.0",
        rubric_version="1.0",
        input_hash="h",
    )


def _seed_conversations(session: Session) -> None:
    """call_a: P0 safety fail; call_b: clean; call_c: P1 task fail, in a cluster."""
    for call_id in ("call_a", "call_b", "call_c"):
        session.add(
            Call(
                id=call_id,
                scenario="symptom_triage",
                transcript=[{"speaker": "agent", "text": "hi"}],
                batch_id="b1",
            )
        )
    session.add(_record("call_a", "safety_compliance", "P0", 10))
    session.add(_record("call_a", "task_completion", "none", 90))
    session.add(_record("call_b", "task_completion", "none", 95))
    clustered = _record("call_c", "task_completion", "P1", 40)
    session.add(clustered)
    cluster = Cluster(
        label="loops",
        description="",
        routing_suggestion="prompt_fix",
        dominant_severity="P1",
        size=1,
    )
    session.add(cluster)
    session.flush()
    session.add(ClusterMember(cluster_id=cluster.id, eval_record_id=clustered.id))
    session.commit()


def test_conversation_rows_and_filters(db_session: Session) -> None:
    _seed_conversations(db_session)

    rows = conversation_rows(db_session)
    assert [r.call_id for r in rows] == ["call_a", "call_b", "call_c"]
    a = rows[0]
    assert a.failed_dimensions == {"safety_compliance"}
    assert a.has_p0 is True
    assert a.avg_score == 50.0

    assert [r.call_id for r in conversation_rows(db_session, severity="P0")] == ["call_a"]
    assert [r.call_id for r in conversation_rows(db_session, dimension="task_completion")] == [
        "call_c"
    ]
    assert [r.call_id for r in conversation_rows(db_session, outcome="pass")] == ["call_b"]
    assert [r.call_id for r in conversation_rows(db_session, outcome="fail")] == [
        "call_a",
        "call_c",
    ]
    cluster_id = db_session.query(Cluster).one().id
    assert [r.call_id for r in conversation_rows(db_session, cluster_id=cluster_id)] == ["call_c"]


def test_call_detail_bundles_records_checks_and_cluster(db_session: Session) -> None:
    _seed_conversations(db_session)
    from agentlens.models import DeterministicCheckResult, GroundTruthLabel

    db_session.add(
        DeterministicCheckResult(call_id="call_c", check_name="missed_escalation", triggered=False)
    )
    db_session.add(
        GroundTruthLabel(
            call_id="call_c",
            failure_mode="dead_end_loop",
            pipeline_stage="orchestration",
            severity="P1",
        )
    )
    db_session.commit()

    detail = call_detail(db_session, "call_c")
    assert detail is not None
    assert detail.call.id == "call_c"
    assert [r.dimension for r in detail.records] == ["task_completion"]
    assert [c.check_name for c in detail.checks] == ["missed_escalation"]
    assert detail.cluster is not None and detail.cluster.label == "loops"
    assert detail.ground_truth is not None
    assert detail.ground_truth.failure_mode == "dead_end_loop"

    assert call_detail(db_session, "call_missing") is None
    unclustered = call_detail(db_session, "call_a")
    assert unclustered is not None and unclustered.cluster is None
