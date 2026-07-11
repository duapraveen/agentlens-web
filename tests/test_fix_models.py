"""Tests for FixProposal and RegressionRun models (US-5)."""

from sqlalchemy.orm import Session

from agentlens.models import Cluster, FixProposal, RegressionRun


def _cluster(session: Session) -> Cluster:
    cluster = Cluster(
        label="missed escalation",
        description="Agent fails to escalate red flags.",
        routing_suggestion="prompt_fix",
        dominant_severity="P0",
        size=3,
    )
    session.add(cluster)
    session.flush()
    return cluster


def test_fix_proposal_roundtrip_with_default_status(db_session: Session) -> None:
    cluster = _cluster(db_session)
    fix = FixProposal(
        cluster_id=cluster.id,
        fix_type="prompt_fix",
        rationale="Escalation rules are buried.",
        patch="Always escalate chest pain to emergency services immediately.",
    )
    db_session.add(fix)
    db_session.commit()

    loaded = db_session.query(FixProposal).one()
    assert loaded.status == "proposed"
    assert loaded.cluster is cluster
    assert cluster.fix_proposals == [loaded]
    assert loaded.created_at is not None


def test_regression_run_roundtrip(db_session: Session) -> None:
    cluster = _cluster(db_session)
    fix = FixProposal(cluster_id=cluster.id, fix_type="prompt_fix", rationale="r", patch="p")
    db_session.add(fix)
    db_session.flush()
    run = RegressionRun(
        fix_proposal_id=fix.id,
        batch_id="fixbatch_1",
        n_before=3,
        n_after=3,
        before_pass_rates={"safety_compliance": 0.0, "task_completion": 0.67},
        after_pass_rates={"safety_compliance": 1.0, "task_completion": 1.0},
        target_dimension="safety_compliance",
        regressed_dimensions=[],
    )
    db_session.add(run)
    db_session.commit()

    loaded = db_session.query(RegressionRun).one()
    assert loaded.fix_proposal is fix
    assert loaded.before_pass_rates["safety_compliance"] == 0.0
    assert loaded.after_pass_rates["task_completion"] == 1.0
    assert loaded.regressed_dimensions == []
