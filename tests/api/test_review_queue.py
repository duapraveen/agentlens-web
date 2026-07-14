"""Review queue GET and POST endpoints."""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from agentlens.models import Call, EvalRecord


def _seed_finding(session: Session) -> int:
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


def test_empty_queue(client: TestClient) -> None:
    response = client.get("/api/review-queue")
    body = response.json()
    assert body["pending_count"] == 0
    assert body["current"] is None


def test_queue_returns_pending_finding(client: TestClient, db_session: Session) -> None:
    _seed_finding(db_session)

    response = client.get("/api/review-queue")
    body = response.json()
    assert body["pending_count"] == 1
    assert body["current"]["call_id"] == "call_1"
    assert body["current"]["dimension"] == "safety_compliance"


def test_submit_review_advances_queue(client: TestClient, db_session: Session) -> None:
    record_id = _seed_finding(db_session)

    response = client.post(
        f"/api/review-queue/{record_id}", json={"verdict": "agree", "note": "looks right"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["pending_count"] == 0
    assert body["stats"]["n_reviews"] == 1


def test_submit_review_rejects_invalid_verdict(client: TestClient, db_session: Session) -> None:
    record_id = _seed_finding(db_session)

    response = client.post(f"/api/review-queue/{record_id}", json={"verdict": "maybe"})
    assert response.status_code == 400
