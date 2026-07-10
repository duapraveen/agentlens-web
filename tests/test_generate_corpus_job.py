"""Tests for the corpus generation job (generate_call stubbed; no LLM calls)."""

from collections.abc import Iterator
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from agentlens.corpus.scenarios import FailureMode, Scenario
from agentlens.jobs.generate_corpus import main, plan_assignments
from agentlens.models import Call, JobRun


@pytest.fixture()
def job_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    """Point the app at a tmp database and tmp log file; yield the db url."""
    url = f"sqlite:///{tmp_path}/job.db"
    monkeypatch.setenv("AGENTLENS_DATABASE_URL", url)
    monkeypatch.setenv("AGENTLENS_JOBS_LOG_PATH", str(tmp_path / "logs" / "jobs.log"))
    yield url


def test_plan_assignments_deterministic_and_exact() -> None:
    plan_a = plan_assignments(20, 0.3, seed=42)
    plan_b = plan_assignments(20, 0.3, seed=42)
    assert plan_a == plan_b
    assert len(plan_a) == 20
    failures = [fm for _, fm in plan_a if fm is not None]
    assert len(failures) == 6  # round(20 * 0.3)
    assert {s for s, _ in plan_a} == set(Scenario)  # 20 calls cover all 5 scenarios


def test_plan_assignments_covers_all_modes_at_default_scope() -> None:
    plan = plan_assignments(60, 0.3, seed=1)
    failures = [fm for _, fm in plan if fm is not None]
    assert len(failures) == 18  # round(60 * 0.3)
    assert set(failures) == set(FailureMode)  # 18 failures cover all 6 modes (3 each)


def _fake_generate_call(
    session: Session, scenario: Scenario, failure_mode: FailureMode | None, batch_id: str
) -> Call:
    call = Call(
        id=f"call_{uuid4().hex[:12]}",
        scenario=scenario.value,
        transcript=[],
        batch_id=batch_id,
    )
    session.add(call)
    session.commit()
    return call


def test_main_runs_job_and_records_jobrun(job_env: str) -> None:
    with patch(
        "agentlens.jobs.generate_corpus.generate_call", side_effect=_fake_generate_call
    ) as mock_gen:
        exit_code = main(["--count", "10", "--failure-rate", "0.3", "--seed", "7"])
    assert exit_code == 0
    assert mock_gen.call_count == 10
    engine = create_engine(job_env)
    with Session(engine) as session:
        run = session.query(JobRun).one()
        assert run.job_name == "generate_corpus"
        assert run.status == "completed"
        assert run.finished_at is not None
        assert run.summary["requested"] == 10
        assert run.summary["generated"] == 10
        assert run.summary["failed"] == 0
        assert run.summary["duration_ms"] >= 0
        assert session.query(Call).count() == 10


def test_main_counts_generation_failures(job_env: str) -> None:
    with patch("agentlens.jobs.generate_corpus.generate_call", return_value=None):
        exit_code = main(["--count", "4", "--seed", "1"])
    assert exit_code == 0
    engine = create_engine(job_env)
    with Session(engine) as session:
        run = session.query(JobRun).one()
        assert run.summary["generated"] == 0
        assert run.summary["failed"] == 4


def test_job_log_file_written(job_env: str, tmp_path: Path) -> None:
    with patch("agentlens.jobs.generate_corpus.generate_call", side_effect=_fake_generate_call):
        main(["--count", "2", "--seed", "1"])
    log_file = tmp_path / "logs" / "jobs.log"
    assert log_file.exists()
    content = log_file.read_text()
    assert "generate_corpus" in content
