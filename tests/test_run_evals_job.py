"""Tests for the eval batch job (evaluate_call stubbed; no LLM calls)."""

from collections.abc import Iterator
from pathlib import Path
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from agentlens.jobs.run_evals import main
from agentlens.models import Base, Call, EvalRecord, JobRun


def _seed_calls(url: str, n: int = 3, pre_evaluated: int = 0, n_golden: int = 0) -> None:
    engine = create_engine(url)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        for i in range(n):
            session.add(
                Call(
                    id=f"call_{i:03d}",
                    scenario="symptom_triage",
                    transcript=[{"speaker": "agent", "text": "hi"}],
                    batch_id="b1",
                    is_golden=i < n_golden,
                )
            )
        for i in range(pre_evaluated):
            for dim in (
                "task_completion",
                "factual_accuracy",
                "safety_compliance",
                "communication_quality",
            ):
                session.add(
                    EvalRecord(
                        call_id=f"call_{i:03d}",
                        dimension=dim,
                        score=90,
                        severity="none",
                        passed=True,
                        judge_reasoning="ok",
                        judge_model="claude-haiku-4-5",
                        prompt_version="1.0",
                        rubric_version="1.0",
                        input_hash="deadbeef00000000",
                    )
                )
        session.commit()


@pytest.fixture()
def job_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    url = f"sqlite:///{tmp_path}/evals.db"
    monkeypatch.setenv("AGENTLENS_DATABASE_URL", url)
    monkeypatch.setenv("AGENTLENS_JOBS_LOG_PATH", str(tmp_path / "logs" / "jobs.log"))
    yield url


def test_unevaluated_scope_skips_already_evaluated(job_env: str) -> None:
    _seed_calls(job_env, n=3, pre_evaluated=1)
    with patch("agentlens.jobs.run_evals.evaluate_call", return_value="created") as mock:
        exit_code = main(["--scope", "unevaluated"])
    assert exit_code == 0
    assert mock.call_count == 2  # call_000 already has records for this judge config


def test_full_scope_visits_every_call_and_records_jobrun(job_env: str) -> None:
    _seed_calls(job_env, n=3, pre_evaluated=1)
    outcomes = iter(["skipped", "created", "failed"])
    with patch(
        "agentlens.jobs.run_evals.evaluate_call", side_effect=lambda *a, **k: next(outcomes)
    ):
        exit_code = main(["--scope", "full"])
    assert exit_code == 0
    engine = create_engine(job_env)
    with Session(engine) as session:
        run = session.query(JobRun).one()
        assert run.job_name == "run_evals"
        assert run.status == "completed"
        assert run.summary["scope"] == "full"
        assert run.summary["evaluated"] == 1
        assert run.summary["skipped"] == 1
        assert run.summary["failed"] == 1
        assert run.summary["cost_cents"] >= 0.0


def test_golden_scope_visits_only_golden_calls(job_env: str) -> None:
    _seed_calls(job_env, n=4, n_golden=2)
    visited: list[str] = []

    def record_id(_session: object, call: Call, **_kwargs: object) -> str:
        visited.append(call.id)
        return "created"

    with patch("agentlens.jobs.run_evals.evaluate_call", side_effect=record_id):
        exit_code = main(["--scope", "golden"])
    assert exit_code == 0
    assert set(visited) == {"call_000", "call_001"}


def test_estimate_is_logged_before_run(job_env: str, tmp_path: Path) -> None:
    _seed_calls(job_env, n=2)
    with patch("agentlens.jobs.run_evals.evaluate_call", return_value="created"):
        main([])
    content = (tmp_path / "logs" / "jobs.log").read_text()
    assert "estimated_cost_cents" in content
