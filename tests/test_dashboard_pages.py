"""AppTest smoke tests for dashboard pages (run standalone against a seeded DB)."""

from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from streamlit.testing.v1 import AppTest

from agentlens.models import Base, Call, EvalRecord, JobRun, utcnow

_PAGES = Path("agentlens/dashboard/pages")


def _seed(url: str) -> None:
    engine = create_engine(url)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(
            Call(
                id="call_dash_1",
                scenario="symptom_triage",
                transcript=[
                    {"speaker": "agent", "text": "Hello, how can I help?"},
                    {"speaker": "patient", "text": "I need an appointment."},
                ],
                batch_id="b1",
            )
        )
        session.add(
            EvalRecord(
                call_id="call_dash_1",
                dimension="task_completion",
                score=40,
                severity="P1",
                passed=False,
                failure_description="left unresolved",
                judge_reasoning="r",
                judge_model="claude-haiku-4-5",
                prompt_version="1.0",
                rubric_version="1.0",
                input_hash="h",
            )
        )
        session.add(
            Call(
                id="call_dash_2",
                scenario="prescription_refill",
                transcript=[{"speaker": "agent", "text": "Hello."}],
                batch_id="b1",
            )
        )
        session.add(
            JobRun(
                job_name="run_evals",
                status="completed",
                finished_at=utcnow(),
                summary={"evaluated": 1, "cost_cents": 0.35, "duration_ms": 1000},
            )
        )
        session.commit()


@pytest.fixture()
def dash_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> str:
    url = f"sqlite:///{tmp_path}/dash.db"
    _seed(url)
    monkeypatch.setenv("AGENTLENS_DATABASE_URL", url)
    monkeypatch.setenv("AGENTLENS_JOBS_LOG_PATH", str(tmp_path / "logs" / "jobs.log"))
    return url


def test_jobs_page_renders_cards_and_estimate(dash_env: str) -> None:
    at = AppTest.from_file(str(_PAGES / "jobs.py"), default_timeout=10)
    at.run()
    assert not at.exception
    assert at.number_input[0].value == 60
    assert at.slider[0].value == 30
    # eval card shows a call-count-based estimate for the unevaluated scope (1 call)
    assert any("1 calls" in c.value for c in at.caption)
    # last-run summary from the seeded JobRun appears
    assert any("evaluated: 1" in c.value for c in at.caption)
