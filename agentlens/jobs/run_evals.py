"""Batch job: evaluate calls with deterministic checks + the LLM judge (US-1).

Usage: python -m agentlens.jobs.run_evals [--scope full|unevaluated] [--model NAME]
"""

import argparse
import time

from sqlalchemy import select

from agentlens.config import get_settings
from agentlens.db import open_session
from agentlens.evals.runner import evaluate_call
from agentlens.jobs._logging import configure_job_logging
from agentlens.llm.gateway import cost_cents
from agentlens.models import Call, EvalRecord, JobRun, LLMCallLog, utcnow
from agentlens.prompts.judge import PROMPT_VERSION

# Rough per-call token estimate for the pre-run cost estimate (short calls).
_EST_INPUT_TOKENS = 1200
_EST_OUTPUT_TOKENS = 500


def main(argv: list[str] | None = None) -> int:
    """Run the eval job; returns a process exit code."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scope", choices=["full", "unevaluated"], default="unevaluated")
    parser.add_argument("--model", default=None)
    args = parser.parse_args(argv)

    settings = get_settings()
    judge_model = args.model or settings.judge_model
    log = configure_job_logging(settings.jobs_log_path)
    started = time.monotonic()

    with open_session() as session:
        if args.scope == "unevaluated":
            evaluated_ids = select(EvalRecord.call_id).where(
                EvalRecord.judge_model == judge_model,
                EvalRecord.prompt_version == PROMPT_VERSION,
            )
            calls = session.query(Call).filter(~Call.id.in_(evaluated_ids)).all()
        else:
            calls = session.query(Call).all()

        estimate = len(calls) * cost_cents(judge_model, _EST_INPUT_TOKENS, _EST_OUTPUT_TOKENS)
        log.info(
            "job_started",
            job="run_evals",
            scope=args.scope,
            model=judge_model,
            calls=len(calls),
            estimated_cost_cents=round(estimate, 2),
        )
        run = JobRun(job_name="run_evals", status="running")
        session.add(run)
        session.commit()
        cost_floor = session.query(LLMCallLog.id).count()

        counts = {"created": 0, "skipped": 0, "failed": 0}
        for call in calls:
            outcome = evaluate_call(session, call, model=judge_model)
            counts[outcome] += 1
            log.info("call_evaluated", call_id=call.id, outcome=outcome)

        actual = (
            session.query(LLMCallLog)
            .filter(LLMCallLog.id > cost_floor, LLMCallLog.purpose == "judge")
            .all()
        )
        run.status = "completed"
        run.finished_at = utcnow()
        run.summary = {
            "scope": args.scope,
            "model": judge_model,
            "evaluated": counts["created"],
            "skipped": counts["skipped"],
            "failed": counts["failed"],
            "cost_cents": round(sum(row.cost_cents for row in actual), 3),
            "duration_ms": int((time.monotonic() - started) * 1000),
        }
        session.commit()
        log.info("job_finished", job="run_evals", **run.summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
