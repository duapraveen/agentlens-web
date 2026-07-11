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


def test_conversations_page_lists_calls_with_filters(dash_env: str) -> None:
    at = AppTest.from_file(str(_PAGES / "conversations.py"), default_timeout=10)
    at.run()
    assert not at.exception
    # only the evaluated call appears (call_dash_2 has no eval records)
    assert any("1 calls · 1 with failures" in c.value for c in at.caption)
    assert [s.label for s in at.selectbox] == ["Severity", "Dimension", "Cluster", "Outcome"]
    # a filter that excludes everything empties the table
    at.selectbox[0].select("P0").run()
    assert any("0 calls" in c.value for c in at.caption)


def test_call_detail_renders_transcript_scores_and_ground_truth_toggle(dash_env: str) -> None:
    at = AppTest.from_file(str(_PAGES / "call_detail.py"), default_timeout=10)
    at.session_state["selected_call_id"] = "call_dash_1"
    at.run()
    assert not at.exception
    assert any("call_dash_1" in h.value for h in at.header)
    assert any("Hello, how can I help?" in m.value for m in at.markdown)
    assert len(at.expander) == 1  # one evaluated dimension
    assert "task_completion" in at.expander[0].label
    # engineer sees the ground-truth toggle; enabling it reports a clean call
    at.toggle[0].set_value(True).run()
    assert not at.exception
    assert any("clean call" in i.value for i in at.info)


def test_call_detail_without_selection_prompts(dash_env: str) -> None:
    at = AppTest.from_file(str(_PAGES / "call_detail.py"), default_timeout=10)
    at.run()
    assert not at.exception
    assert any("Select a call" in i.value for i in at.info)


def test_clusters_page_renders_cards_with_p0_guard(dash_env: str) -> None:
    from agentlens.db import open_session
    from agentlens.models import Cluster

    with open_session() as session:
        session.add(
            Cluster(
                label="phi exposure",
                description="Agent reads back PHI.",
                routing_suggestion="prompt_fix",
                dominant_severity="P0",
                size=2,
            )
        )
        session.commit()

    at = AppTest.from_file(str(_PAGES / "clusters.py"), default_timeout=10)
    at.run()
    assert not at.exception
    assert any("1 clusters · 2 failures" in c.value for c in at.caption)
    assert any("phi exposure" in s.value for s in at.subheader)
    fix_buttons = [b for b in at.button if b.label == "Propose Fix"]
    assert len(fix_buttons) == 1 and fix_buttons[0].disabled  # P0 guard


def test_review_queue_submit_advances_to_clear(dash_env: str) -> None:
    at = AppTest.from_file(str(_PAGES / "review_queue.py"), default_timeout=10)
    at.run()
    assert not at.exception
    # the seeded P1 finding is pending
    assert any("call_dash_1" in s.value for s in at.subheader)
    assert at.button[0].disabled  # Submit & Next disabled until a verdict is chosen
    at.radio[0].set_value("Agree")
    at.text_area[0].set_value("confirmed").run()
    at.button[0].click().run()
    assert not at.exception
    assert any("Queue clear" in s.value for s in at.success)

    from agentlens.db import open_session
    from agentlens.models import Review

    with open_session() as session:
        review = session.query(Review).one()
        assert review.verdict == "agree"
        assert review.note == "confirmed"


def test_overview_renders_all_panels(dash_env: str) -> None:
    at = AppTest.from_file(str(_PAGES / "overview.py"), default_timeout=10)
    at.run()
    assert not at.exception
    assert [s.value for s in at.subheader] == [
        "Quality",
        "Severity",
        "Judge Accuracy",
        "Top Clusters",
    ]
    # severity counts from the seed: one P1 finding
    assert any("P1: 1 findings" in b.label for b in at.button)
    assert any("Total eval cost to date" in c.value for c in at.caption)


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
