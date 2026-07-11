"""Tests for judge-human agreement stats (AC-4.2)."""

from sqlalchemy.orm import Session

from agentlens.feedback.calibration import compute_agreement
from agentlens.models import Call, EvalRecord, Review


def _reviewed_finding(
    session: Session,
    call_id: str,
    dimension: str,
    verdict: str,
    prompt_version: str = "1.0",
) -> None:
    session.add(
        Call(
            id=call_id,
            scenario="symptom_triage",
            transcript=[{"speaker": "agent", "text": "hi"}],
            batch_id="b1",
        )
    )
    record = EvalRecord(
        call_id=call_id,
        dimension=dimension,
        score=30,
        severity="P1",
        passed=False,
        failure_description="issue",
        judge_reasoning="r",
        judge_model="claude-haiku-4-5",
        prompt_version=prompt_version,
        rubric_version="1.0",
        input_hash="h",
    )
    session.add(record)
    session.flush()
    session.add(Review(eval_record_id=record.id, verdict=verdict))


def test_overall_and_per_dimension_agreement(db_session: Session) -> None:
    _reviewed_finding(db_session, "c1", "safety_compliance", "agree")
    _reviewed_finding(db_session, "c2", "safety_compliance", "agree")
    _reviewed_finding(db_session, "c3", "task_completion", "disagree")
    db_session.commit()

    stats = compute_agreement(db_session)
    assert stats.n_reviews == 3
    assert stats.n_agree == 2
    assert stats.agreement == 2 / 3
    assert stats.per_dimension == {"safety_compliance": 1.0, "task_completion": 0.0}
    assert stats.per_dimension_counts == {"safety_compliance": 2, "task_completion": 1}


def test_no_reviews_is_all_zeros(db_session: Session) -> None:
    stats = compute_agreement(db_session)
    assert stats.n_reviews == 0
    assert stats.agreement == 0.0
    assert stats.per_dimension == {}


def test_judge_config_filter(db_session: Session) -> None:
    _reviewed_finding(db_session, "c1", "safety_compliance", "agree", prompt_version="1.0")
    _reviewed_finding(db_session, "c2", "safety_compliance", "disagree", prompt_version="1.1")
    db_session.commit()

    v10 = compute_agreement(db_session, judge_model="claude-haiku-4-5", prompt_version="1.0")
    assert (v10.n_reviews, v10.agreement) == (1, 1.0)
    v11 = compute_agreement(db_session, judge_model="claude-haiku-4-5", prompt_version="1.1")
    assert (v11.n_reviews, v11.agreement) == (1, 0.0)
