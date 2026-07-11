"""Batch job: draft a fix proposal for one cluster (US-5, AC-5.1).

Usage: python -m agentlens.jobs.propose_fix --cluster-id N [--model NAME]
"""

import argparse
import time

from agentlens.config import get_settings
from agentlens.db import open_session
from agentlens.fixes.propose import propose_fix
from agentlens.jobs._logging import configure_job_logging
from agentlens.models import Cluster, FixProposal, JobRun, utcnow


def main(argv: list[str] | None = None) -> int:
    """Draft and persist one FixProposal; returns a process exit code."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cluster-id", type=int, required=True)
    parser.add_argument("--model", default=None)
    args = parser.parse_args(argv)

    settings = get_settings()
    log = configure_job_logging(settings.jobs_log_path)
    started = time.monotonic()

    with open_session() as session:
        run = JobRun(job_name="propose_fix", status="running")
        session.add(run)
        session.commit()

        cluster = session.get(Cluster, args.cluster_id)
        if cluster is None:
            run.status = "failed"
            run.finished_at = utcnow()
            run.summary = {"error": f"cluster {args.cluster_id} not found"}
            session.commit()
            log.error("job_failed", job="propose_fix", cluster_id=args.cluster_id)
            return 1

        result = propose_fix(session, cluster, model=args.model)
        if not result.success or result.parsed is None:
            run.status = "failed"
            run.finished_at = utcnow()
            run.summary = {"cluster_id": cluster.id, "error": result.error}
            session.commit()
            log.error("job_failed", job="propose_fix", cluster_id=cluster.id)
            return 1

        fix = FixProposal(
            cluster_id=cluster.id,
            fix_type=result.parsed.fix_type,
            rationale=result.parsed.rationale,
            patch=result.parsed.patch,
        )
        session.add(fix)
        session.flush()
        run.status = "completed"
        run.finished_at = utcnow()
        run.summary = {
            "cluster_id": cluster.id,
            "fix_id": fix.id,
            "fix_type": fix.fix_type,
            "cost_cents": round(result.cost_cents, 3),
            "duration_ms": int((time.monotonic() - started) * 1000),
        }
        session.commit()
        log.info("job_finished", job="propose_fix", **run.summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
