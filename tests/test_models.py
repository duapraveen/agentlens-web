"""Tests for ORM models and engine helpers."""

from pathlib import Path

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from agentlens.db import create_db_engine, open_session
from agentlens.models import Call, GroundTruthLabel, JobRun, LLMCallLog


def _make_call(call_id: str = "call_abc123") -> Call:
    return Call(
        id=call_id,
        scenario="symptom_triage",
        transcript=[
            {"speaker": "patient", "text": "I have a headache."},
            {"speaker": "agent", "text": "How long has it lasted?"},
        ],
        batch_id="batch_1",
    )


def test_call_roundtrip(db_session: Session) -> None:
    db_session.add(_make_call())
    db_session.commit()
    loaded = db_session.get(Call, "call_abc123")
    assert loaded is not None
    assert loaded.transcript[0]["speaker"] == "patient"
    assert loaded.is_golden is False
    assert loaded.agent_prompt_version == "v1"
    assert loaded.ground_truth is None


def test_ground_truth_label_links_to_call(db_session: Session) -> None:
    call = _make_call()
    db_session.add(call)
    db_session.add(
        GroundTruthLabel(
            call_id=call.id,
            failure_mode="missed_escalation",
            pipeline_stage="reasoning",
            severity="P0",
        )
    )
    db_session.commit()
    assert call.ground_truth is not None
    assert call.ground_truth.severity == "P0"


def test_one_label_per_call(db_session: Session) -> None:
    call = _make_call()
    db_session.add(call)
    for _ in range(2):
        db_session.add(
            GroundTruthLabel(
                call_id=call.id,
                failure_mode="dead_end_loop",
                pipeline_stage="orchestration",
                severity="P1",
            )
        )
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_llm_call_log_and_job_run(db_session: Session) -> None:
    db_session.add(
        LLMCallLog(
            purpose="corpus_generation",
            model="claude-sonnet-5",
            prompt_name="corpus_generation",
            prompt_version="1.0",
            input_tokens=100,
            output_tokens=500,
            cost_cents=0.105,
            success=True,
        )
    )
    db_session.add(JobRun(job_name="generate_corpus", status="running", summary={}))
    db_session.commit()
    log = db_session.query(LLMCallLog).one()
    assert log.cost_cents == pytest.approx(0.105)
    run = db_session.query(JobRun).one()
    assert run.finished_at is None


def test_create_db_engine_creates_sqlite_parent_dir(tmp_path: Path) -> None:
    url = f"sqlite:///{tmp_path}/nested/dir/app.db"
    create_db_engine(url)
    assert (tmp_path / "nested" / "dir" / "app.db").exists()


def test_open_session_usable(tmp_path: Path) -> None:
    with open_session(f"sqlite:///{tmp_path}/s.db") as session:
        session.add(_make_call("call_open"))
        session.commit()
        assert session.get(Call, "call_open") is not None
