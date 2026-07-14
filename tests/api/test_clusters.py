"""Clusters list endpoint."""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from agentlens.models import Cluster


def test_list_clusters_empty(client: TestClient) -> None:
    response = client.get("/api/clusters")
    assert response.status_code == 200
    assert response.json() == {"cards": [], "n_failures": 0, "last_clustered_at": None}


def test_list_clusters_returns_seeded_cluster(client: TestClient, db_session: Session) -> None:
    db_session.add(
        Cluster(
            label="Missed escalations",
            description="Agent fails to escalate red-flag symptoms.",
            routing_suggestion="prompt_fix",
            dominant_severity="P0",
            size=3,
        )
    )
    db_session.commit()

    response = client.get("/api/clusters")
    body = response.json()
    assert body["n_failures"] == 3
    assert body["cards"][0]["label"] == "Missed escalations"
    assert body["cards"][0]["is_p0"] is True


def test_list_clusters_filters_by_severity(client: TestClient, db_session: Session) -> None:
    db_session.add(
        Cluster(
            label="P1 cluster",
            description="",
            routing_suggestion="ops_process",
            dominant_severity="P1",
            size=2,
        )
    )
    db_session.commit()

    response = client.get("/api/clusters", params={"severity": "P0"})
    assert response.json()["cards"] == []
