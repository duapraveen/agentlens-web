"""Conversations list and detail endpoints."""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from agentlens.models import Call, EvalRecord


def _seed_call(session: Session, call_id: str) -> None:
    session.add(
        Call(
            id=call_id,
            scenario="symptom_triage",
            transcript=[{"speaker": "patient", "text": "hi"}],
            batch_id="b1",
        )
    )
    session.add(
        EvalRecord(
            call_id=call_id,
            dimension="safety_compliance",
            score=40,
            severity="P0",
            passed=False,
            failure_description="missed escalation",
            judge_reasoning="reasoning text",
            judge_model="claude-haiku-4-5",
            prompt_version="v1",
            rubric_version="v1",
            input_hash="abc123",
        )
    )
    session.commit()


def test_list_conversations_empty(client: TestClient) -> None:
    response = client.get("/api/conversations")
    assert response.status_code == 200
    body = response.json()
    assert body == {"rows": [], "total": 0, "clusters": []}


def test_list_conversations_returns_seeded_call(client: TestClient, db_session: Session) -> None:
    _seed_call(db_session, "call_1")

    response = client.get("/api/conversations")
    body = response.json()
    assert body["total"] == 1
    assert body["rows"][0]["call_id"] == "call_1"
    assert body["rows"][0]["has_p0"] is True


def test_get_conversation_detail_not_found(client: TestClient) -> None:
    response = client.get("/api/conversations/does_not_exist")
    assert response.status_code == 404


def test_get_conversation_detail_found(client: TestClient, db_session: Session) -> None:
    _seed_call(db_session, "call_1")

    response = client.get("/api/conversations/call_1")
    assert response.status_code == 200
    body = response.json()
    assert body["call_id"] == "call_1"
    assert body["records"][0]["dimension"] == "safety_compliance"
    assert body["cluster"] is None
    assert body["ground_truth"] is None
