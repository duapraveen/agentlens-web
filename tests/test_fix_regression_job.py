"""Tests for the run_fix_regression job (regeneration and evaluation patched)."""

from collections.abc import Iterator
from pathlib import Path
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from agentlens.jobs.run_fix_regression import main
from agentlens.models import (
    Base,
    Call,
    Cluster,
    ClusterMember,
    EvalRecord,
    FixProposal,
    JobRun,
    RegressionRun,
)

_MODEL = "claude-haiku-4-5"


def _record(call_id: str, dim: str, passed: bool) -> EvalRecord:
    return EvalRecord(
        call_id=call_id,
        dimension=dim,
        score=90 if passed else 20,
        severity="none" if passed else "P0",
        passed=passed,
        judge_reasoning="r",
        judge_model=_MODEL,
        prompt_version="1.0",
        rubric_version="1.0",
        input_hash="h",
    )


def _seed(url: str) -> int:
    engine = create_engine(url)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        cluster = Cluster(
            label="l",
            description="d",
            routing_suggestion="prompt_fix",
            dominant_severity="P0",
            size=1,
        )
        session.add(cluster)
        session.flush()
        session.add(
            Call(
                id="call_before",
                scenario="symptom_triage",
                transcript=[{"speaker": "agent", "text": "hi"}],
                batch_id="b1",
            )
        )
        record = _record("call_before", "safety_compliance", passed=False)
        session.add(record)
        session.flush()
        session.add(ClusterMember(cluster_id=cluster.id, eval_record_id=record.id))
        fix = FixProposal(cluster_id=cluster.id, fix_type="prompt_fix", rationale="r", patch="p")
        session.add(fix)
        session.commit()
        return fix.id


@pytest.fixture()
def job_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[int]:
    url = f"sqlite:///{tmp_path}/fixreg.db"
    monkeypatch.setenv("AGENTLENS_DATABASE_URL", url)
    monkeypatch.setenv("AGENTLENS_JOBS_LOG_PATH", str(tmp_path / "logs" / "jobs.log"))
    yield _seed(url)


def test_job_regenerates_evaluates_and_reports(job_env: int) -> None:
    def fake_regenerate(session: Session, fix: FixProposal, **_kwargs: object) -> list[Call]:
        call = Call(
            id="call_after",
            scenario="symptom_triage",
            transcript=[{"speaker": "agent", "text": "hi"}],
            batch_id=f"fixbatch_{fix.id}",
            agent_prompt_version=f"fix_{fix.id}",
        )
        session.add(call)
        session.add(_record("call_after", "safety_compliance", passed=True))
        session.commit()
        return [call]

    with (
        patch("agentlens.jobs.run_fix_regression.regenerate_for_fix", side_effect=fake_regenerate),
        patch("agentlens.jobs.run_fix_regression.evaluate_call", return_value="skipped"),
    ):
        assert main(["--fix-id", str(job_env)]) == 0

    from agentlens.db import open_session

    with open_session() as session:
        run = session.query(RegressionRun).one()
        assert run.fix_proposal_id == job_env
        assert run.after_pass_rates["safety_compliance"] == 1.0
        assert session.get(FixProposal, job_env).status == "validated"  # type: ignore[union-attr]
        job = session.query(JobRun).one()
        assert job.summary["fix_id"] == job_env
        assert job.summary["regenerated"] == 1


def test_job_exits_1_on_unknown_fix(job_env: int) -> None:
    assert main(["--fix-id", "9999"]) == 1
