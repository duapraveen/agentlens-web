"""Tests for the recluster job (embedding model and labeling patched; no LLM calls)."""

from collections.abc import Iterator
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from agentlens.clustering.labeling import ClusterLabel
from agentlens.jobs.recluster import main
from agentlens.llm.gateway import GatewayResult
from agentlens.models import Base, Call, Cluster, ClusterMember, EvalRecord, JobRun

_DESCRIPTIONS = [
    "Agent offered an appointment slot that was never established as available.",
    "Agent invented availability and presented a fabricated appointment slot.",
    "Agent repeated the same clarifying question three times despite answers.",
    "Agent looped on the same menu question and never completed the task.",
    "Patient reported chest pain and the agent did not escalate to emergency care.",
    "Agent ignored a red-flag symptom and failed to escalate the call.",
]


def _seed(url: str) -> None:
    engine = create_engine(url)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        for i, desc in enumerate(_DESCRIPTIONS):
            call_id = f"call_{i:03d}"
            session.add(
                Call(
                    id=call_id,
                    scenario="symptom_triage",
                    transcript=[{"speaker": "agent", "text": "hi"}],
                    batch_id="b1",
                )
            )
            session.add(
                EvalRecord(
                    call_id=call_id,
                    dimension="safety_compliance" if "escalate" in desc else "task_completion",
                    score=30,
                    severity="P0" if "escalate" in desc else "P1",
                    pipeline_stage="reasoning",
                    passed=False,
                    failure_description=desc,
                    judge_reasoning="r",
                    judge_model="claude-haiku-4-5",
                    prompt_version="1.0",
                    rubric_version="1.0",
                    input_hash="h",
                )
            )
        session.commit()


@pytest.fixture()
def job_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    url = f"sqlite:///{tmp_path}/cluster.db"
    monkeypatch.setenv("AGENTLENS_DATABASE_URL", url)
    monkeypatch.setenv("AGENTLENS_JOBS_LOG_PATH", str(tmp_path / "logs" / "jobs.log"))
    _seed(url)
    yield url


def _fake_embed(texts: list[str]) -> np.ndarray:
    """Keyword-keyed unit vectors plus a per-row epsilon so all points are distinct."""

    def base(text: str) -> list[float]:
        if "escalate" in text:
            return [0.0, 0.0, 1.0]
        if "slot" in text or "availab" in text:
            return [1.0, 0.0, 0.0]
        return [0.0, 1.0, 0.0]

    rows = [base(t) for t in texts]
    return np.asarray(rows) + np.arange(len(rows)).reshape(-1, 1) * 1e-3


def _fake_label(*args: object, **kwargs: object) -> GatewayResult[ClusterLabel]:
    return GatewayResult(
        parsed=ClusterLabel(
            label="some pattern", description="A recurring pattern.", routing="prompt_fix"
        ),
        success=True,
        error=None,
        cost_cents=0.05,
    )


def test_recluster_builds_labeled_clusters(job_env: str) -> None:
    with (
        patch("agentlens.jobs.recluster.embed_texts", side_effect=_fake_embed),
        patch("agentlens.jobs.recluster.label_cluster", side_effect=_fake_label),
    ):
        assert main([]) == 0
    engine = create_engine(job_env)
    with Session(engine) as session:
        clusters = session.query(Cluster).all()
        assert len(clusters) >= 2
        assert sum(c.size for c in clusters) == 6
        assert session.query(ClusterMember).count() == 6
        for c in clusters:
            assert c.label == "some pattern"
            assert c.routing_suggestion == "prompt_fix"
            assert c.dominant_severity in ("P0", "P1")
        run = session.query(JobRun).one()
        assert run.summary["failures"] == 6
        assert run.summary["clusters"] == len(clusters)


def test_recluster_embeds_dimension_and_stage_context(job_env: str) -> None:
    """Embedding input carries judge metadata so clusters group by mechanism, not topic."""
    captured: list[str] = []

    def spy(texts: list[str]) -> np.ndarray:
        captured.extend(texts)
        return _fake_embed(texts)

    with (
        patch("agentlens.jobs.recluster.embed_texts", side_effect=spy),
        patch("agentlens.jobs.recluster.label_cluster", side_effect=_fake_label),
    ):
        assert main([]) == 0
    assert len(captured) == 6
    assert all(t.startswith("dimension: ") and "stage: reasoning." in t for t in captured)
    assert any(t.endswith(_DESCRIPTIONS[0]) for t in captured)


def test_recluster_is_rebuild_not_append(job_env: str) -> None:
    with (
        patch("agentlens.jobs.recluster.embed_texts", side_effect=_fake_embed),
        patch("agentlens.jobs.recluster.label_cluster", side_effect=_fake_label),
    ):
        main([])
        main([])
    engine = create_engine(job_env)
    with Session(engine) as session:
        assert session.query(ClusterMember).count() == 6  # no dupes after re-run
        assert session.query(JobRun).count() == 2


def test_labeling_failure_uses_fallback(job_env: str) -> None:
    failed: GatewayResult[ClusterLabel] = GatewayResult(
        parsed=None, success=False, error="boom", cost_cents=0.0
    )
    with (
        patch("agentlens.jobs.recluster.embed_texts", side_effect=_fake_embed),
        patch("agentlens.jobs.recluster.label_cluster", return_value=failed),
    ):
        assert main([]) == 0
    engine = create_engine(job_env)
    with Session(engine) as session:
        for cluster in session.query(Cluster).all():
            assert cluster.label.startswith("unlabeled_cluster_")
            assert cluster.routing_suggestion == "ops_process"
