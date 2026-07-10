"""Batch job: compute judge quality vs golden and store the regression baseline.

Usage: python -m agentlens.jobs.judge_metrics [--model NAME] [--prompt-version V]

The stored JobRun (job_name="judge_metrics") summary is the baseline the
eval regression gate compares against (constitution IV.3).
"""

import argparse
import json
import time
from dataclasses import asdict

from agentlens.config import get_settings
from agentlens.db import open_session
from agentlens.evals.metrics import compute_judge_quality
from agentlens.jobs._logging import configure_job_logging
from agentlens.models import JobRun, utcnow
from agentlens.prompts.judge import PROMPT_VERSION


def main(argv: list[str] | None = None) -> int:
    """Compute and persist golden-set judge quality; returns a process exit code."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default=None)
    parser.add_argument("--prompt-version", default=PROMPT_VERSION)
    args = parser.parse_args(argv)

    settings = get_settings()
    judge_model = args.model or settings.judge_model
    log = configure_job_logging(settings.jobs_log_path)
    started = time.monotonic()

    with open_session() as session:
        quality = compute_judge_quality(session, judge_model, args.prompt_version)
        summary = asdict(quality)
        summary["duration_ms"] = int((time.monotonic() - started) * 1000)
        session.add(
            JobRun(
                job_name="judge_metrics",
                status="completed",
                summary=summary,
                finished_at=utcnow(),
            )
        )
        session.commit()
        log.info("job_finished", job="judge_metrics", **summary)
        print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
