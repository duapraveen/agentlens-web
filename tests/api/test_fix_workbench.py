"""Fix Workbench endpoints: cluster listing, lookup, and P0/404 guards."""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from agentlens.models import Cluster


def test_list_selectable_clusters_excludes_p0(client: TestClient, db_session: Session) -> None:
    db_session.add(
        Cluster(label="P0 cluster", description="", routing_suggestion="prompt_fix",
                 dominant_severity="P0", size=1)
    )
    db_session.add(
        Cluster(label="P1 cluster", description="", routing_suggestion="prompt_fix",
                 dominant_severity="P1", size=2)
    )
    db_session.commit()

    response = client.get("/api/fix-workbench/clusters")
    labels = [c["label"] for c in response.json()]
    assert labels == ["P1 cluster"]


def test_get_fix_workbench_not_found(client: TestClient) -> None:
    response = client.get("/api/fix-workbench/999")
    assert response.status_code == 404


def test_get_fix_workbench_no_fix_yet(client: TestClient, db_session: Session) -> None:
    cluster = Cluster(
        label="P1 cluster", description="d", routing_suggestion="prompt_fix",
        dominant_severity="P1", size=2,
    )
    db_session.add(cluster)
    db_session.commit()

    response = client.get(f"/api/fix-workbench/{cluster.id}")
    body = response.json()
    assert body["fix"] is None
    assert body["regression"] is None
    assert body["cluster"]["label"] == "P1 cluster"


def test_apply_regression_blocked_on_p0_cluster(client: TestClient, db_session: Session) -> None:
    cluster = Cluster(
        label="P0 cluster", description="", routing_suggestion="prompt_fix",
        dominant_severity="P0", size=1,
    )
    db_session.add(cluster)
    db_session.commit()

    response = client.post(f"/api/fix-workbench/{cluster.id}/apply-regression")
    assert response.status_code == 400


def test_apply_regression_requires_a_fix(client: TestClient, db_session: Session) -> None:
    cluster = Cluster(
        label="P1 cluster", description="", routing_suggestion="prompt_fix",
        dominant_severity="P1", size=1,
    )
    db_session.add(cluster)
    db_session.commit()

    response = client.post(f"/api/fix-workbench/{cluster.id}/apply-regression")
    assert response.status_code == 400
