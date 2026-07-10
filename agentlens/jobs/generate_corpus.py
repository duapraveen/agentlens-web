"""Batch job: generate a synthetic corpus with injected failures (US-7).

Usage: python -m agentlens.jobs.generate_corpus --count 60 --failure-rate 0.3 [--seed N]
"""

import argparse
import random
import time
from itertools import cycle
from uuid import uuid4

from agentlens.config import get_settings
from agentlens.corpus.generator import generate_call
from agentlens.corpus.scenarios import FailureMode, Scenario
from agentlens.db import open_session
from agentlens.jobs._logging import configure_job_logging
from agentlens.models import JobRun, utcnow


def plan_assignments(
    count: int, failure_rate: float, seed: int | None
) -> list[tuple[Scenario, FailureMode | None]]:
    """Deterministic per-call plan: scenarios cycled evenly then shuffled; exactly
    round(count * failure_rate) calls get a failure mode, modes cycled evenly."""
    rng = random.Random(seed)
    scenarios = [s for s, _ in zip(cycle(Scenario), range(count), strict=False)]
    rng.shuffle(scenarios)
    n_failures = round(count * failure_rate)
    failure_indices = set(rng.sample(range(count), n_failures)) if n_failures else set()
    modes = cycle(sorted(FailureMode))
    return [
        (scenario, next(modes) if i in failure_indices else None)
        for i, scenario in enumerate(scenarios)
    ]


def main(argv: list[str] | None = None) -> int:
    """Run the corpus generation job; returns a process exit code."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=int, default=60)
    parser.add_argument("--failure-rate", type=float, default=0.3)
    parser.add_argument("--seed", type=int, default=None)
    args = parser.parse_args(argv)

    settings = get_settings()
    log = configure_job_logging(settings.jobs_log_path)
    batch_id = f"batch_{uuid4().hex[:8]}"
    started = time.monotonic()

    with open_session() as session:
        run = JobRun(job_name="generate_corpus", status="running")
        session.add(run)
        session.commit()
        log.info("job_started", job="generate_corpus", batch_id=batch_id, count=args.count)

        generated = failed = 0
        for scenario, failure_mode in plan_assignments(args.count, args.failure_rate, args.seed):
            call = generate_call(session, scenario, failure_mode, batch_id)
            if call is None:
                failed += 1
                log.warning("call_generation_failed", scenario=scenario.value)
            else:
                generated += 1
                log.info(
                    "call_generated",
                    call_id=call.id,
                    scenario=scenario.value,
                    failure_mode=failure_mode.value if failure_mode else None,
                )

        run.status = "completed"
        run.finished_at = utcnow()
        run.summary = {
            "batch_id": batch_id,
            "requested": args.count,
            "generated": generated,
            "failed": failed,
            "duration_ms": int((time.monotonic() - started) * 1000),
        }
        session.commit()
        log.info("job_finished", job="generate_corpus", **run.summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
