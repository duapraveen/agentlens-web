"""Jobs page (Engineer): trigger corpus generation, eval runs, and clustering."""

import subprocess
import sys

import streamlit as st

from agentlens.config import get_settings
from agentlens.dashboard.data import last_job_run, n_calls_for_scope, tail_log
from agentlens.db import open_session
from agentlens.llm.gateway import cost_cents
from agentlens.models import JobRun

_JUDGE_EST_TOKENS = (1200, 500)  # matches jobs/run_evals.py estimate


def _launch(module: str, *args: str) -> None:
    """Start a batch job detached; progress lands in the job log panel below."""
    subprocess.Popen([sys.executable, "-m", module, *args])
    st.success(f"Started `{module}` — follow progress in the job log below.")


def _summary_line(run: JobRun | None, fields: list[str]) -> str:
    if run is None or run.finished_at is None:
        return "No completed runs yet."
    parts = [f"Last run {run.finished_at.strftime('%Y-%m-%d %H:%M')}"]
    parts += [f"{f}: {run.summary.get(f, '—')}" for f in fields]
    return " · ".join(parts)


st.header("Jobs")

with open_session() as session:
    corpus_run = last_job_run(session, "generate_corpus")
    eval_run = last_job_run(session, "run_evals")
    cluster_run = last_job_run(session, "recluster")

    with st.container(border=True):
        st.subheader("Corpus Generation")
        count = st.number_input("Call count", min_value=1, max_value=500, value=60)
        rate = st.slider("Failure injection rate (%)", 0, 100, 30)
        if st.button("Generate Corpus"):
            _launch(
                "agentlens.jobs.generate_corpus",
                "--count",
                str(count),
                "--failure-rate",
                str(rate / 100),
            )
        st.caption(_summary_line(corpus_run, ["generated", "failed", "duration_ms"]))

    with st.container(border=True):
        st.subheader("Eval Run")
        scope_label = st.radio("Scope", ["Unevaluated only", "Full corpus"], horizontal=True)
        scope = "unevaluated" if scope_label == "Unevaluated only" else "full"
        model = st.selectbox("Judge model", ["claude-haiku-4-5", "claude-sonnet-5"])
        n = n_calls_for_scope(session, scope, model)  # type: ignore[arg-type]
        estimate = n * cost_cents(model, *_JUDGE_EST_TOKENS)
        st.caption(f"Estimated: {n} calls ≈ {estimate / 100:.2f} USD")
        if st.button("Run Evals"):
            _launch("agentlens.jobs.run_evals", "--scope", scope, "--model", model)
        st.caption(_summary_line(eval_run, ["evaluated", "cost_cents", "duration_ms"]))

    with st.container(border=True):
        st.subheader("Clustering")
        if st.button("Re-cluster Failures"):
            _launch("agentlens.jobs.recluster")
        st.caption(_summary_line(cluster_run, ["clusters", "failures", "cost_cents"]))

st.subheader("Job log")
with st.container(height=200):
    lines = tail_log(get_settings().jobs_log_path, n=20)
    st.text("\n".join(lines) if lines else "No job log yet.")
