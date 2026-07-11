"""Tests for the success-metrics verification job (spec §2). No LLM calls."""

from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from agentlens.jobs.verify_metrics import main
from agentlens.models import (
    Base,
    Call,
    Cluster,
    ClusterMember,
    EvalRecord,
    FixProposal,
    GroundTruthLabel,
    JobRun,
    LLMCallLog,
    RegressionRun,
    Review,
)

_MODEL = "claude-haiku-4-5"


def _seed_all_pass(url: str, judge_cost_cents: float = 0.4) -> None:
    """Minimal DB where every spec §2 metric passes outright."""
    engine = create_engine(url)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        cluster = Cluster(
            label="loops",
            description="d",
            routing_suggestion="prompt_fix",
            dominant_severity="P1",
            size=1,
        )
        session.add(cluster)
        session.flush()
        # one injected golden failure, judged correctly; one clean golden call
        for call_id, injected in (("g1", True), ("g2", False)):
            session.add(
                Call(
                    id=call_id,
                    scenario="symptom_triage",
                    transcript=[{"speaker": "agent", "text": "hi"}],
                    batch_id="b1",
                    is_golden=True,
                )
            )
            if injected:
                session.add(
                    GroundTruthLabel(
                        call_id=call_id,
                        failure_mode="dead_end_loop",
                        pipeline_stage="orchestration",
                        severity="P1",
                    )
                )
            record = EvalRecord(
                call_id=call_id,
                dimension="task_completion",
                score=30 if injected else 95,
                severity="P1" if injected else "none",
                passed=not injected,
                failure_description="issue" if injected else None,
                judge_reasoning="r",
                judge_model=_MODEL,
                prompt_version="1.0",
                rubric_version="1.0",
                input_hash="h",
            )
            session.add(record)
            session.flush()
            if injected:
                session.add(ClusterMember(cluster_id=cluster.id, eval_record_id=record.id))
                session.add(Review(eval_record_id=record.id, verdict="agree"))
        fix = FixProposal(
            cluster_id=cluster.id,
            fix_type="prompt_fix",
            rationale="r",
            patch="p",
            status="validated",
        )
        session.add(fix)
        session.flush()
        session.add(
            RegressionRun(
                fix_proposal_id=fix.id,
                batch_id=f"fixbatch_{fix.id}",
                n_before=1,
                n_after=1,
                before_pass_rates={"task_completion": 0.0},
                after_pass_rates={"task_completion": 1.0},
                target_dimension="task_completion",
                regressed_dimensions=[],
            )
        )
        session.add(
            LLMCallLog(
                purpose="judge",
                model=_MODEL,
                prompt_name="judge",
                prompt_version="1.0",
                cost_cents=judge_cost_cents,
            )
        )
        session.commit()


@pytest.fixture()
def job_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> str:
    url = f"sqlite:///{tmp_path}/verify.db"
    monkeypatch.setenv("AGENTLENS_DATABASE_URL", url)
    monkeypatch.setenv("AGENTLENS_JOBS_LOG_PATH", str(tmp_path / "logs" / "jobs.log"))
    return url


def _summary(url: str) -> dict[str, object]:
    engine = create_engine(url)
    with Session(engine) as session:
        run = session.query(JobRun).filter(JobRun.job_name == "verify_metrics").one()
        assert run.summary is not None
        return dict(run.summary)


def test_all_metrics_pass_exits_0(job_env: str) -> None:
    _seed_all_pass(job_env)
    assert main([]) == 0
    summary = _summary(job_env)
    statuses = {m["name"]: m["status"] for m in summary["metrics"]}  # type: ignore[union-attr, index, call-overload]
    assert statuses == {
        "judge_precision": "PASS",
        "judge_recall": "PASS",
        "cluster_purity": "PASS",
        "agreement_visible": "PASS",
        "closed_loop_demo": "PASS",
        "cost_per_call": "PASS",
    }


def test_unaccepted_failure_exits_1(job_env: str) -> None:
    # judge cost of 600 cents for 2 evaluated calls -> 300 cents/call >> 5 cents target
    _seed_all_pass(job_env, judge_cost_cents=600.0)
    assert main([]) == 1
    summary = _summary(job_env)
    statuses = {m["name"]: m["status"] for m in summary["metrics"]}  # type: ignore[union-attr, index, call-overload]
    assert statuses["cost_per_call"] == "FAIL"
