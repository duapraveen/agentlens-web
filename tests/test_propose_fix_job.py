"""Tests for the propose_fix batch job (propose_fix patched; no LLM calls)."""

from collections.abc import Iterator
from pathlib import Path
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from agentlens.fixes.propose import ProposedFix
from agentlens.jobs.propose_fix import main
from agentlens.llm.gateway import GatewayResult
from agentlens.models import Base, Cluster, FixProposal, JobRun


def _seed_cluster(url: str) -> int:
    engine = create_engine(url)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        cluster = Cluster(
            label="missed cardiac escalation",
            description="d",
            routing_suggestion="prompt_fix",
            dominant_severity="P0",
            size=3,
        )
        session.add(cluster)
        session.commit()
        return cluster.id


@pytest.fixture()
def job_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[int]:
    url = f"sqlite:///{tmp_path}/fixes.db"
    monkeypatch.setenv("AGENTLENS_DATABASE_URL", url)
    monkeypatch.setenv("AGENTLENS_JOBS_LOG_PATH", str(tmp_path / "logs" / "jobs.log"))
    yield _seed_cluster(url)


_FIX = ProposedFix(fix_type="prompt_fix", rationale="rationale", patch="patch text")


def test_job_persists_fix_proposal(job_env: int) -> None:
    ok: GatewayResult[ProposedFix] = GatewayResult(
        parsed=_FIX, success=True, error=None, cost_cents=0.1
    )
    with patch("agentlens.jobs.propose_fix.propose_fix", return_value=ok):
        assert main(["--cluster-id", str(job_env)]) == 0

    from agentlens.db import open_session

    with open_session() as session:
        fix = session.query(FixProposal).one()
        assert fix.cluster_id == job_env
        assert fix.fix_type == "prompt_fix"
        assert fix.patch == "patch text"
        assert fix.status == "proposed"
        run = session.query(JobRun).one()
        assert run.summary["fix_id"] == fix.id


def test_job_exits_1_on_gateway_failure(job_env: int) -> None:
    failed: GatewayResult[ProposedFix] = GatewayResult(
        parsed=None, success=False, error="boom", cost_cents=0.0
    )
    with patch("agentlens.jobs.propose_fix.propose_fix", return_value=failed):
        assert main(["--cluster-id", str(job_env)]) == 1

    from agentlens.db import open_session

    with open_session() as session:
        assert session.query(FixProposal).count() == 0


def test_job_exits_1_on_unknown_cluster(job_env: int) -> None:
    assert main(["--cluster-id", "9999"]) == 1
