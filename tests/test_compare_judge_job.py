"""Tests for the compare_judge batch job (no LLM calls; pure DB computation)."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from agentlens.jobs.compare_judge import main
from agentlens.models import Base, Call, EvalRecord, GroundTruthLabel, JobRun

_MODEL = "claude-haiku-4-5"


def _seed(url: str) -> None:
    engine = create_engine(url)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
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
        # baseline v1.0 catches the injected failure; candidate v1.1 misses it
        for version, flagged in (("1.0", True), ("1.1", False)):
            for call_id in ("g1", "g2"):
                hit = flagged and call_id == "g1"
                session.add(
                    EvalRecord(
                        call_id=call_id,
                        dimension="task_completion",
                        score=30 if hit else 95,
                        severity="P1" if hit else "none",
                        passed=not hit,
                        judge_reasoning="r",
                        judge_model=_MODEL,
                        prompt_version=version,
                        rubric_version=version,
                        input_hash="h",
                    )
                )
        session.commit()


@pytest.fixture()
def job_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    url = f"sqlite:///{tmp_path}/compare.db"
    monkeypatch.setenv("AGENTLENS_DATABASE_URL", url)
    monkeypatch.setenv("AGENTLENS_JOBS_LOG_PATH", str(tmp_path / "logs" / "jobs.log"))
    _seed(url)
    yield url


def test_regression_returns_exit_code_1_and_records_jobrun(job_env: str) -> None:
    exit_code = main(["--baseline", "1.0", "--candidate", "1.1"])
    assert exit_code == 1
    engine = create_engine(job_env)
    with Session(engine) as session:
        run = session.query(JobRun).one()
        assert run.job_name == "compare_judge"
        assert run.status == "completed"
        assert run.summary["regression_flagged"] is True
        assert run.summary["recall_delta"] == -1.0
        assert run.summary["baseline"] == "1.0"
        assert run.summary["candidate"] == "1.1"


def test_non_regressing_comparison_exits_0(job_env: str) -> None:
    assert main(["--baseline", "1.0", "--candidate", "1.0"]) == 0
