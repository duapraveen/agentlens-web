"""Smoke test for the FastAPI app factory and health endpoint."""

from fastapi.testclient import TestClient

from agentlens.api.main import app


def test_health_returns_ok() -> None:
    client = TestClient(app)
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
