"""Jobs endpoints: launch batch jobs, report their status, tail the job log."""

import subprocess
import sys
from typing import Literal

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from agentlens.api.deps import get_db
from agentlens.api.schemas import (
    EvalEstimateOut,
    GenerateCorpusIn,
    JobsStatusOut,
    JobSummaryOut,
    RunEvalsIn,
)
from agentlens.config import get_settings
from agentlens.dashboard.data import last_job_run, n_calls_for_scope, tail_log
from agentlens.llm.gateway import cost_cents

router = APIRouter(tags=["jobs"])

_JUDGE_EST_TOKENS = (1200, 500)


def _summary_out(session: Session, job_name: str) -> JobSummaryOut:
    run = last_job_run(session, job_name)
    return JobSummaryOut(
        finished_at=run.finished_at if run else None,
        summary=run.summary if run else {},
    )


@router.get("/jobs/status", response_model=JobsStatusOut)
def jobs_status(session: Session = Depends(get_db)) -> JobsStatusOut:  # noqa: B008
    return JobsStatusOut(
        corpus=_summary_out(session, "generate_corpus"),
        evals=_summary_out(session, "run_evals"),
        cluster=_summary_out(session, "recluster"),
        log_lines=tail_log(get_settings().jobs_log_path, n=20),
    )


@router.get("/jobs/eval-estimate", response_model=EvalEstimateOut)
def eval_estimate(
    scope: Literal["full", "unevaluated"], model: str, session: Session = Depends(get_db)  # noqa: B008
) -> EvalEstimateOut:
    n = n_calls_for_scope(session, scope, model)
    return EvalEstimateOut(n_calls=n, estimate_cents=n * cost_cents(model, *_JUDGE_EST_TOKENS))


@router.post("/jobs/corpus", status_code=202)
def launch_corpus(body: GenerateCorpusIn) -> dict[str, str]:
    subprocess.Popen(
        [
            sys.executable,
            "-m",
            "agentlens.jobs.generate_corpus",
            "--count",
            str(body.count),
            "--failure-rate",
            str(body.failure_rate),
        ]
    )
    return {"status": "started"}


@router.post("/jobs/evals", status_code=202)
def launch_evals(body: RunEvalsIn) -> dict[str, str]:
    subprocess.Popen(
        [
            sys.executable,
            "-m",
            "agentlens.jobs.run_evals",
            "--scope",
            body.scope,
            "--model",
            body.model,
        ]
    )
    return {"status": "started"}


@router.post("/jobs/recluster", status_code=202)
def launch_recluster() -> dict[str, str]:
    subprocess.Popen([sys.executable, "-m", "agentlens.jobs.recluster"])
    return {"status": "started"}
