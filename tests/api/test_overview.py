"""Overview and status endpoints."""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from agentlens.models import Call


def test_status_empty_db(client: TestClient) -> None:
    response = client.get("/api/status")
    assert response.status_code == 200
    body = response.json()
    assert body == {"last_eval_at": None, "n_calls": 0, "n_golden": 0}


def test_status_counts_calls(client: TestClient, db_session: Session) -> None:
    db_session.add(Call(id="call_1", scenario="symptom_triage", transcript=[], batch_id="b1"))
    db_session.add(
        Call(
            id="call_2",
            scenario="symptom_triage",
            transcript=[],
            batch_id="b1",
            is_golden=True,
        )
    )
    db_session.commit()

    response = client.get("/api/status")
    body = response.json()
    assert body["n_calls"] == 2
    assert body["n_golden"] == 1


def test_overview_shape_on_empty_db(client: TestClient) -> None:
    response = client.get("/api/overview")
    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {
        "quality",
        "severities",
        "precision",
        "recall",
        "agreement",
        "n_reviews",
        "top_clusters",
        "total_eval_cents",
        "avg_per_call_cents",
        "failure_trend",
    }
    assert body["n_reviews"] == 0
    assert body["top_clusters"] == []
    assert body["failure_trend"] == []
