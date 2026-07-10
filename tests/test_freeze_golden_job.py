"""Tests for the golden-set freeze job (AC-7.4; data/golden is append-only)."""

import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from agentlens.jobs.freeze_golden import main, select_golden
from agentlens.models import Base, Call, GroundTruthLabel, JobRun

_SCENARIOS = [
    "appointment_scheduling",
    "symptom_triage",
    "insurance_eligibility",
    "prescription_refill",
    "referral_navigation",
]
_MODES = [
    ("missed_escalation", "reasoning", "P0"),
    ("dead_end_loop", "orchestration", "P1"),
    ("wrong_retrieval", "retrieval", "P1"),
]


def _seed_corpus(session: Session, n_clean: int = 42, n_failed: int = 18) -> None:
    for i in range(n_clean):
        session.add(
            Call(
                id=f"call_clean_{i:03d}",
                scenario=_SCENARIOS[i % 5],
                transcript=[{"speaker": "agent", "text": "hello"}],
                batch_id="b1",
            )
        )
    for i in range(n_failed):
        call_id = f"call_fail_{i:03d}"
        mode, stage, sev = _MODES[i % 3]
        session.add(
            Call(
                id=call_id,
                scenario=_SCENARIOS[i % 5],
                transcript=[{"speaker": "agent", "text": "hello"}],
                batch_id="b1",
            )
        )
        session.add(
            GroundTruthLabel(call_id=call_id, failure_mode=mode, pipeline_stage=stage, severity=sev)
        )
    session.commit()


@pytest.fixture()
def golden_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[tuple[str, Path]]:
    url = f"sqlite:///{tmp_path}/golden.db"
    golden_dir = tmp_path / "golden"
    monkeypatch.setenv("AGENTLENS_DATABASE_URL", url)
    monkeypatch.setenv("AGENTLENS_GOLDEN_DIR", str(golden_dir))
    monkeypatch.setenv("AGENTLENS_JOBS_LOG_PATH", str(tmp_path / "logs" / "jobs.log"))
    engine = create_engine(url)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        _seed_corpus(session)
    yield url, golden_dir


def test_select_golden_stratifies_across_groups(db_session: Session) -> None:
    _seed_corpus(db_session)
    calls = db_session.query(Call).all()
    selected = select_golden(calls, 20)
    assert len(selected) == 20
    selected_groups = {
        (c.scenario, c.ground_truth.failure_mode if c.ground_truth else "clean") for c in selected
    }
    # 5 clean groups + up to 15 (scenario, mode) failure groups exist; round-robin
    # over 20 groups picking 20 must touch every group at least once
    assert len(selected_groups) == 20


def test_select_golden_caps_at_corpus_size(db_session: Session) -> None:
    _seed_corpus(db_session, n_clean=3, n_failed=0)
    calls = db_session.query(Call).all()
    assert len(select_golden(calls, 50)) == 3


def test_main_marks_and_exports(golden_env: tuple[str, Path]) -> None:
    url, golden_dir = golden_env
    exit_code = main(["--count", "50"])
    assert exit_code == 0
    engine = create_engine(url)
    with Session(engine) as session:
        golden_calls = session.query(Call).filter(Call.is_golden).all()
        assert len(golden_calls) == 50
        run = session.query(JobRun).one()
        assert run.status == "completed"
        assert run.summary["frozen"] == 50
    files = sorted(golden_dir.glob("*.json"))
    assert len(files) == 50
    record = json.loads(files[0].read_text())
    assert set(record) == {"call", "ground_truth"}
    assert record["call"]["id"].startswith("call_")


def test_rerun_is_append_only(golden_env: tuple[str, Path]) -> None:
    _, golden_dir = golden_env
    main(["--count", "50"])
    first = {p.name: p.read_text() for p in golden_dir.glob("*.json")}
    exit_code = main(["--count", "50"])  # rerun: already-golden calls are skipped
    assert exit_code == 0
    second = {p.name: p.read_text() for p in golden_dir.glob("*.json")}
    for name, content in first.items():
        assert second[name] == content  # nothing modified
