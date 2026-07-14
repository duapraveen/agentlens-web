"""Jobs status, eval-estimate, and job-launch endpoints."""

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient


def test_jobs_status_empty_db(client: TestClient) -> None:
    response = client.get("/api/jobs/status")
    assert response.status_code == 200
    body = response.json()
    assert body["corpus"] == {"finished_at": None, "summary": {}}
    assert body["log_lines"] == []


def test_eval_estimate_empty_db(client: TestClient) -> None:
    response = client.get(
        "/api/jobs/eval-estimate", params={"scope": "full", "model": "claude-haiku-4-5"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["n_calls"] == 0
    assert body["estimate_cents"] == 0.0


def test_launch_corpus_starts_subprocess(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    mock_popen = MagicMock()
    monkeypatch.setattr("agentlens.api.routers.jobs.subprocess.Popen", mock_popen)

    response = client.post("/api/jobs/corpus", json={"count": 10, "failure_rate": 0.3})
    assert response.status_code == 202
    assert response.json() == {"status": "started"}
    mock_popen.assert_called_once()
    args = mock_popen.call_args[0][0]
    assert "agentlens.jobs.generate_corpus" in args
    assert "--count" in args
    assert "10" in args
    assert "--failure-rate" in args
    assert "0.3" in args


def test_launch_evals_starts_subprocess(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    mock_popen = MagicMock()
    monkeypatch.setattr("agentlens.api.routers.jobs.subprocess.Popen", mock_popen)

    response = client.post(
        "/api/jobs/evals", json={"scope": "unevaluated", "model": "claude-haiku-4-5"}
    )
    assert response.status_code == 202
    mock_popen.assert_called_once()
    args = mock_popen.call_args[0][0]
    assert "agentlens.jobs.run_evals" in args
    assert "--scope" in args
    assert "unevaluated" in args
    assert "--model" in args
    assert "claude-haiku-4-5" in args


def test_launch_recluster_starts_subprocess(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    mock_popen = MagicMock()
    monkeypatch.setattr("agentlens.api.routers.jobs.subprocess.Popen", mock_popen)

    response = client.post("/api/jobs/recluster")
    assert response.status_code == 202
    mock_popen.assert_called_once()
    args = mock_popen.call_args[0][0]
    assert "agentlens.jobs.recluster" in args
