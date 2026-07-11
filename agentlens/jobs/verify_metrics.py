"""Batch job: verify the spec §2 success metrics against the live database (T701).

Usage: python -m agentlens.jobs.verify_metrics

Each metric reports PASS, FAIL, or ACCEPTED. ACCEPTED marks a shortfall the
user explicitly signed off on (recorded in plan.md exit results) — thresholds
are never silently lowered. Exit code is 1 only when an unaccepted FAIL exists.
No LLM calls; pure DB computation.
"""

import argparse
import time
from typing import Any

from sqlalchemy.orm import Session

from agentlens.clustering.purity import compute_mode_purity
from agentlens.config import get_settings
from agentlens.db import open_session
from agentlens.evals.metrics import compute_judge_quality
from agentlens.feedback.calibration import compute_agreement
from agentlens.jobs._logging import configure_job_logging
from agentlens.models import EvalRecord, FixProposal, JobRun, LLMCallLog, RegressionRun, utcnow
from agentlens.prompts.judge import PROMPT_VERSION

# User-accepted deviations (2026-07-10, see plan.md Phase 2 and Phase 3 exit results).
_ACCEPTED_RECALL_FLOOR = 0.72
_ACCEPTED_PURITY = {"hallucinated_availability": 0.66}

_COST_TARGET_CENTS = 5.0


def _metric(name: str, value: Any, status: str, detail: str) -> dict[str, Any]:
    return {"name": name, "value": value, "status": status, "detail": detail}


def _judge_metrics(session: Session, judge_model: str) -> list[dict[str, Any]]:
    quality = compute_judge_quality(session, judge_model, PROMPT_VERSION)
    precision_ok = quality.precision >= 0.80
    if quality.recall >= 0.80:
        recall_status, recall_detail = "PASS", ""
    elif quality.recall >= _ACCEPTED_RECALL_FLOOR:
        recall_status = "ACCEPTED"
        recall_detail = "user-accepted 2026-07-10: transcript-only judge (plan.md Phase 2)"
    else:
        recall_status, recall_detail = "FAIL", "below the accepted 0.72 floor"
    return [
        _metric(
            "judge_precision",
            round(quality.precision, 3),
            "PASS" if precision_ok else "FAIL",
            "target ≥ 0.80",
        ),
        _metric("judge_recall", round(quality.recall, 3), recall_status, recall_detail),
    ]


def _purity_metric(session: Session) -> dict[str, Any]:
    purity = compute_mode_purity(session)
    failing = {m: p for m, p in purity.items() if p < 0.90}
    if not failing:
        return _metric("cluster_purity", purity, "PASS", "all modes ≥ 0.90")
    unaccepted = {m: p for m, p in failing.items() if p < _ACCEPTED_PURITY.get(m, 0.90)}
    if not unaccepted:
        return _metric(
            "cluster_purity",
            purity,
            "ACCEPTED",
            f"user-accepted 2026-07-10: {sorted(failing)} (plan.md Phase 3)",
        )
    return _metric("cluster_purity", purity, "FAIL", f"unaccepted modes: {sorted(unaccepted)}")


def _agreement_metric(session: Session) -> dict[str, Any]:
    stats = compute_agreement(session)
    detail = f"n_reviews={stats.n_reviews}" + (
        "" if stats.n_reviews else " (no human reviews submitted yet)"
    )
    return _metric("agreement_visible", round(stats.agreement, 3), "PASS", detail)


def _closed_loop_metric(session: Session) -> dict[str, Any]:
    fix = session.query(FixProposal).filter(FixProposal.status.in_(["validated", "closed"])).first()
    run = session.query(RegressionRun).first() if fix else None
    ok = fix is not None and run is not None and bool(run.after_pass_rates)
    detail = (
        f"fix {fix.id} ({fix.status}) with regression run {run.id}"
        if ok and fix is not None and run is not None
        else "no validated fix with a regression run"
    )
    return _metric("closed_loop_demo", ok, "PASS" if ok else "FAIL", detail)


def _cost_metric(session: Session) -> dict[str, Any]:
    total = sum(
        row.cost_cents for row in session.query(LLMCallLog).filter(LLMCallLog.purpose == "judge")
    )
    n_calls = session.query(EvalRecord.call_id).distinct().count()
    per_call = total / n_calls if n_calls else 0.0
    ok = n_calls > 0 and per_call < _COST_TARGET_CENTS
    return _metric(
        "cost_per_call",
        round(per_call, 3),
        "PASS" if ok else "FAIL",
        f"target < {_COST_TARGET_CENTS}¢; {n_calls} evaluated calls",
    )


def main(argv: list[str] | None = None) -> int:
    """Verify all spec §2 metrics; returns 1 when any unaccepted FAIL exists."""
    argparse.ArgumentParser(description=__doc__).parse_args(argv)
    settings = get_settings()
    log = configure_job_logging(settings.jobs_log_path)
    started = time.monotonic()

    with open_session() as session:
        run = JobRun(job_name="verify_metrics", status="running")
        session.add(run)
        session.commit()

        metrics = [
            *_judge_metrics(session, settings.judge_model),
            _purity_metric(session),
            _agreement_metric(session),
            _closed_loop_metric(session),
            _cost_metric(session),
        ]
        for m in metrics:
            log.info("metric", **m)

        all_ok = all(m["status"] != "FAIL" for m in metrics)
        run.status = "completed"
        run.finished_at = utcnow()
        run.summary = {
            "metrics": metrics,
            "all_ok": all_ok,
            "duration_ms": int((time.monotonic() - started) * 1000),
        }
        session.commit()
        log.info("job_finished", job="verify_metrics", all_ok=all_ok)
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
