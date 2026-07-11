"""Tests for the before/after regression report and P0 close guard (AC-5.3, AC-5.4)."""

import pytest
from sqlalchemy.orm import Session

from agentlens.fixes.report import build_regression_run, close_fix, pass_rates
from agentlens.models import Call, Cluster, ClusterMember, EvalRecord, FixProposal

_MODEL = "claude-haiku-4-5"


def _call_with_records(
    session: Session, call_id: str, dim_passed: dict[str, bool], batch_id: str = "b1"
) -> Call:
    call = Call(
        id=call_id,
        scenario="symptom_triage",
        transcript=[{"speaker": "agent", "text": "hi"}],
        batch_id=batch_id,
    )
    session.add(call)
    for dim, passed in dim_passed.items():
        session.add(
            EvalRecord(
                call_id=call_id,
                dimension=dim,
                score=90 if passed else 20,
                severity="none" if passed else "P1",
                passed=passed,
                failure_description=None if passed else "issue",
                judge_reasoning="r",
                judge_model=_MODEL,
                prompt_version="1.0",
                rubric_version="1.0",
                input_hash="h",
            )
        )
    session.flush()
    return call


def _fix_with_members(session: Session, severity: str = "P1") -> FixProposal:
    cluster = Cluster(
        label="l",
        description="d",
        routing_suggestion="prompt_fix",
        dominant_severity=severity,
        size=2,
    )
    session.add(cluster)
    session.flush()
    for i in range(2):
        call = _call_with_records(
            session,
            f"call_before_{i}",
            {"safety_compliance": False, "communication_quality": True},
        )
        record = next(r for r in call.eval_records if r.dimension == "safety_compliance")
        session.add(ClusterMember(cluster_id=cluster.id, eval_record_id=record.id))
    fix = FixProposal(cluster_id=cluster.id, fix_type="prompt_fix", rationale="r", patch="p")
    session.add(fix)
    session.commit()
    return fix


def test_pass_rates_per_dimension(db_session: Session) -> None:
    a = _call_with_records(db_session, "c1", {"safety_compliance": True, "task_completion": False})
    b = _call_with_records(db_session, "c2", {"safety_compliance": False, "task_completion": True})
    db_session.commit()

    rates = pass_rates([a, b], _MODEL, "1.0")
    assert rates == {"safety_compliance": 0.5, "task_completion": 0.5}


def test_regression_run_flags_only_non_target_regressions(db_session: Session) -> None:
    fix = _fix_with_members(db_session)
    # after: target dimension fixed, unrelated dimension regressed
    after = [
        _call_with_records(
            db_session,
            f"call_after_{i}",
            {"safety_compliance": True, "communication_quality": False},
            batch_id=f"fixbatch_{fix.id}",
        )
        for i in range(2)
    ]
    db_session.commit()

    run = build_regression_run(db_session, fix, after)
    assert run.target_dimension == "safety_compliance"
    assert run.before_pass_rates["safety_compliance"] == 0.0
    assert run.after_pass_rates["safety_compliance"] == 1.0
    assert run.regressed_dimensions == ["communication_quality"]
    assert run.n_before == 2 and run.n_after == 2
    assert fix.status == "validated"


def test_close_fix_p0_guard(db_session: Session) -> None:
    p0_fix = _fix_with_members(db_session, severity="P0")
    with pytest.raises(PermissionError):
        close_fix(db_session, p0_fix, actor="auto")
    assert p0_fix.status != "closed"
    close_fix(db_session, p0_fix, actor="human")
    assert p0_fix.status == "closed"


def test_close_fix_auto_allowed_for_non_p0(db_session: Session) -> None:
    p1_fix = _fix_with_members(db_session, severity="P1")
    close_fix(db_session, p1_fix, actor="auto")
    assert p1_fix.status == "closed"
