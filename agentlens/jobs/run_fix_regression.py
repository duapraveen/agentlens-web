"""Batch job: validate one fix via regenerate + re-eval + before/after report (US-5).

Usage: python -m agentlens.jobs.run_fix_regression --fix-id N
"""

import argparse
import time

from agentlens.config import get_settings
from agentlens.db import open_session
from agentlens.evals.runner import evaluate_call
from agentlens.fixes.regression import affected_calls, regenerate_for_fix
from agentlens.fixes.report import build_regression_run
from agentlens.jobs._logging import configure_job_logging
from agentlens.llm.gateway import cost_cents
from agentlens.models import FixProposal, JobRun, LLMCallLog, utcnow

# Rough per-call token estimates for the pre-run cost estimate.
_GEN_INPUT_TOKENS, _GEN_OUTPUT_TOKENS = 600, 700
_JUDGE_INPUT_TOKENS, _JUDGE_OUTPUT_TOKENS = 1200, 500


def main(argv: list[str] | None = None) -> int:
    """Run the fix regression loop; returns a process exit code."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fix-id", type=int, required=True)
    args = parser.parse_args(argv)

    settings = get_settings()
    log = configure_job_logging(settings.jobs_log_path)
    started = time.monotonic()

    with open_session() as session:
        run = JobRun(job_name="run_fix_regression", status="running")
        session.add(run)
        session.commit()

        fix = session.get(FixProposal, args.fix_id)
        if fix is None:
            run.status = "failed"
            run.finished_at = utcnow()
            run.summary = {"error": f"fix {args.fix_id} not found"}
            session.commit()
            log.error("job_failed", job="run_fix_regression", fix_id=args.fix_id)
            return 1

        n_affected = len(affected_calls(session, fix.cluster))
        estimate = n_affected * (
            cost_cents(settings.generator_model, _GEN_INPUT_TOKENS, _GEN_OUTPUT_TOKENS)
            + cost_cents(settings.judge_model, _JUDGE_INPUT_TOKENS, _JUDGE_OUTPUT_TOKENS)
        )
        log.info(
            "job_started",
            job="run_fix_regression",
            fix_id=fix.id,
            affected_calls=n_affected,
            estimated_cost_cents=round(estimate, 2),
        )
        cost_floor = session.query(LLMCallLog.id).count()

        regenerated = regenerate_for_fix(session, fix)
        evaluated = sum(1 for call in regenerated if evaluate_call(session, call) == "created")
        report = build_regression_run(session, fix, regenerated)

        actual = (
            session.query(LLMCallLog)
            .filter(
                LLMCallLog.id > cost_floor,
                LLMCallLog.purpose.in_(["fix_regeneration", "judge"]),
            )
            .all()
        )
        run.status = "completed"
        run.finished_at = utcnow()
        run.summary = {
            "fix_id": fix.id,
            "regenerated": len(regenerated),
            "evaluated": evaluated,
            "target_dimension": report.target_dimension,
            "before_pass_rates": report.before_pass_rates,
            "after_pass_rates": report.after_pass_rates,
            "regressed_dimensions": report.regressed_dimensions,
            "cost_cents": round(sum(row.cost_cents for row in actual), 3),
            "duration_ms": int((time.monotonic() - started) * 1000),
        }
        session.commit()
        log.info("job_finished", job="run_fix_regression", **run.summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
