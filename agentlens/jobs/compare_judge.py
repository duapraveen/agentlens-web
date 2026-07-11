"""Batch job: compare two judge prompt versions on the golden set (US-4, AC-4.3).

Usage: python -m agentlens.jobs.compare_judge --baseline 1.0 --candidate 1.1 [--model NAME]

Pure DB computation (no LLM calls) — run the candidate first via
`run_evals --scope golden`. Exit code 1 when the regression gate trips
(constitution IV.3), so this can block a merge.
"""

import argparse
import time

from agentlens.config import get_settings
from agentlens.db import open_session
from agentlens.feedback.compare import compare_judge_versions
from agentlens.jobs._logging import configure_job_logging
from agentlens.models import JobRun, utcnow


def main(argv: list[str] | None = None) -> int:
    """Run the comparison; returns 1 when the regression gate flags, else 0."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", required=True)
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--model", default=None)
    args = parser.parse_args(argv)

    settings = get_settings()
    judge_model = args.model or settings.judge_model
    log = configure_job_logging(settings.jobs_log_path)
    started = time.monotonic()

    with open_session() as session:
        run = JobRun(job_name="compare_judge", status="running")
        session.add(run)
        session.commit()

        result = compare_judge_versions(session, judge_model, args.baseline, args.candidate)
        run.status = "completed"
        run.finished_at = utcnow()
        run.summary = {
            "model": judge_model,
            "baseline": args.baseline,
            "candidate": args.candidate,
            "baseline_precision": result.baseline.precision,
            "baseline_recall": result.baseline.recall,
            "candidate_precision": result.candidate.precision,
            "candidate_recall": result.candidate.recall,
            "baseline_agreement": result.baseline_agreement.agreement,
            "candidate_agreement": result.candidate_agreement.agreement,
            "precision_delta": result.precision_delta,
            "recall_delta": result.recall_delta,
            "regression_flagged": result.regression_flagged,
            "duration_ms": int((time.monotonic() - started) * 1000),
        }
        session.commit()
        log.info("job_finished", job="compare_judge", **run.summary)
    return 1 if result.regression_flagged else 0


if __name__ == "__main__":
    raise SystemExit(main())
