"""Review queue GET and POST endpoints."""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from agentlens.models import Call, EvalRecord


def _seed_finding(session: Session) -> int:
    """One call with a single failing safety_compliance record."""
    session.add(
        Call(
            id="call_1",
            scenario="symptom_triage",
            transcript=[{"speaker": "a", "text": "x"}],
            batch_id="b1",
        )
    )
    record = EvalRecord(
        call_id="call_1",
        dimension="safety_compliance",
        score=20,
        severity="P0",
        passed=False,
        failure_description="missed escalation",
        judge_reasoning="reasoning",
        judge_model="claude-haiku-4-5",
        prompt_version="v1",
        rubric_version="v1",
        input_hash="abc123",
    )
    session.add(record)
    session.commit()
    return record.id


def _seed_call_with_four_dimensions(session: Session) -> tuple[str, int, int]:
    """One call with a failing safety_compliance record and a passing task_completion one.

    Returns (call_id, failing_record_id, passing_record_id).
    """
    session.add(
        Call(
            id="call_multi",
            scenario="symptom_triage",
            transcript=[{"speaker": "a", "text": "x"}],
            batch_id="b1",
        )
    )
    failing = EvalRecord(
        call_id="call_multi",
        dimension="safety_compliance",
        score=20,
        severity="P0",
        passed=False,
        failure_description="missed escalation",
        judge_reasoning="reasoning",
        judge_model="claude-haiku-4-5",
        prompt_version="v1",
        rubric_version="v1",
        input_hash="abc123",
    )
    passing = EvalRecord(
        call_id="call_multi",
        dimension="task_completion",
        score=90,
        severity="none",
        passed=True,
        failure_description=None,
        judge_reasoning="all good",
        judge_model="claude-haiku-4-5",
        prompt_version="v1",
        rubric_version="v1",
        input_hash="abc123",
    )
    session.add_all([failing, passing])
    session.commit()
    return "call_multi", failing.id, passing.id


def test_empty_queue(client: TestClient) -> None:
    response = client.get("/api/review-queue")
    body = response.json()
    assert body["pending_count"] == 0
    assert body["current"] is None


def test_queue_returns_all_dimension_records_for_the_call(
    client: TestClient, db_session: Session
) -> None:
    call_id, failing_id, passing_id = _seed_call_with_four_dimensions(db_session)

    response = client.get("/api/review-queue")
    body = response.json()
    assert body["pending_count"] == 1
    assert body["current"]["call_id"] == call_id

    record_ids = {r["id"]: r for r in body["current"]["records"]}
    assert set(record_ids) == {failing_id, passing_id}
    assert record_ids[failing_id]["dimension"] == "safety_compliance"
    assert record_ids[failing_id]["passed"] is False
    assert record_ids[failing_id]["review"] is None
    assert record_ids[passing_id]["dimension"] == "task_completion"
    assert record_ids[passing_id]["passed"] is True


def test_submit_review_on_a_passing_record_is_recorded(
    client: TestClient, db_session: Session
) -> None:
    _, failing_id, passing_id = _seed_call_with_four_dimensions(db_session)

    response = client.post(
        f"/api/review-queue/{passing_id}",
        json={"verdict": "disagree", "note": "should have failed communication too"},
    )
    assert response.status_code == 200
    body = response.json()
    # the queue is still driven by the unreviewed failing record, not fully advanced
    assert body["current"]["call_id"] is not None
    record_ids = {r["id"]: r for r in body["current"]["records"]}
    assert record_ids[passing_id]["review"] == {
        "verdict": "disagree",
        "note": "should have failed communication too",
    }
    assert record_ids[failing_id]["review"] is None
    assert body["stats"]["n_reviews"] == 1


def test_submit_review_advances_queue(client: TestClient, db_session: Session) -> None:
    record_id = _seed_finding(db_session)

    response = client.post(
        f"/api/review-queue/{record_id}", json={"verdict": "agree", "note": "looks right"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["pending_count"] == 0
    assert body["current"] is None
    assert body["stats"]["n_reviews"] == 1


def test_submit_review_rejects_invalid_verdict(client: TestClient, db_session: Session) -> None:
    record_id = _seed_finding(db_session)

    response = client.post(f"/api/review-queue/{record_id}", json={"verdict": "maybe"})
    assert response.status_code == 400
