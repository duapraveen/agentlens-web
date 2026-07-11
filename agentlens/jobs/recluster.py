"""Batch job: rebuild failure clusters from failed eval records (US-2).

Usage: python -m agentlens.jobs.recluster

Clusters are derived data: every run deletes and rebuilds `clusters` and
`cluster_members`. Labeling failures degrade to a fallback label and never
fail the run.
"""

import argparse
import time

from sqlalchemy.orm import Session

from agentlens.clustering.cluster import assign_clusters
from agentlens.clustering.embed import embed_texts
from agentlens.clustering.labeling import label_cluster
from agentlens.clustering.purity import compute_mode_purity
from agentlens.config import get_settings
from agentlens.db import open_session
from agentlens.jobs._logging import configure_job_logging
from agentlens.models import Cluster, ClusterMember, EvalRecord, JobRun, utcnow

_SEVERITY_ORDER = ["P0", "P1", "P2"]


def _embedding_text(record: EvalRecord) -> str:
    """Prefix judge metadata so embeddings group by failure mechanism, not surface topic."""
    return (
        f"dimension: {record.dimension}. stage: {record.pipeline_stage}. "
        f"{record.failure_description or ''}"
    )


def _dominant_severity(records: list[EvalRecord]) -> str:
    severities = {r.severity for r in records}
    return next((s for s in _SEVERITY_ORDER if s in severities), "P2")


def _build_cluster(
    session: Session, index: int, records: list[EvalRecord], cost: list[float]
) -> Cluster:
    descriptions = [r.failure_description or "" for r in records]
    cluster = Cluster(
        label=f"unlabeled_cluster_{index}",
        description="",
        routing_suggestion="ops_process",
        dominant_severity=_dominant_severity(records),
        size=len(records),
    )
    result = label_cluster(session, descriptions)
    cost.append(result.cost_cents)
    if result.success and result.parsed is not None:
        cluster.label = result.parsed.label
        cluster.description = result.parsed.description
        cluster.routing_suggestion = result.parsed.routing
    session.add(cluster)
    session.flush()
    for record in records:
        session.add(ClusterMember(cluster_id=cluster.id, eval_record_id=record.id))
    return cluster


def main(argv: list[str] | None = None) -> int:
    """Run the recluster job; returns a process exit code."""
    argparse.ArgumentParser(description=__doc__).parse_args(argv)
    settings = get_settings()
    log = configure_job_logging(settings.jobs_log_path)
    started = time.monotonic()

    with open_session() as session:
        run = JobRun(job_name="recluster", status="running")
        session.add(run)
        session.commit()

        failures = (
            session.query(EvalRecord)
            .filter(~EvalRecord.passed, EvalRecord.failure_description.is_not(None))
            .order_by(EvalRecord.id)
            .all()
        )
        session.query(ClusterMember).delete()
        session.query(Cluster).delete()
        session.commit()

        cost: list[float] = []
        n_clusters = 0
        if failures:
            assignments = assign_clusters(embed_texts([_embedding_text(r) for r in failures]))
            groups: dict[int, list[EvalRecord]] = {}
            for record, assigned in zip(failures, assignments, strict=True):
                groups.setdefault(assigned, []).append(record)
            for index, records in sorted(groups.items()):
                cluster = _build_cluster(session, index, records, cost)
                log.info(
                    "cluster_built",
                    cluster_id=cluster.id,
                    label=cluster.label,
                    size=cluster.size,
                    routing=cluster.routing_suggestion,
                )
            n_clusters = len(groups)
        session.commit()

        purity = compute_mode_purity(session)
        run.status = "completed"
        run.finished_at = utcnow()
        run.summary = {
            "clusters": n_clusters,
            "failures": len(failures),
            "purity": purity,
            "cost_cents": round(sum(cost), 3),
            "duration_ms": int((time.monotonic() - started) * 1000),
        }
        session.commit()
        log.info("job_finished", job="recluster", **run.summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
