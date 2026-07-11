"""Overview page (all roles): aggregate quality health, default landing (AC-6.1, AC-6.2)."""

import streamlit as st

from agentlens.dashboard.data import (
    cluster_cards,
    cost_totals,
    last_job_run,
    quality_panel,
    severity_counts,
)
from agentlens.db import open_session
from agentlens.feedback.calibration import compute_agreement

st.header("Overview")

with open_session() as session:
    quality = quality_panel(session)
    severities = severity_counts(session)
    agreement = compute_agreement(session)
    metrics_run = last_job_run(session, "judge_metrics")
    top = cluster_cards(session)[:5]
    costs = cost_totals(session)

top_left, top_right = st.columns(2)

with top_left.container(border=True):
    st.subheader("Quality")
    for dim, q in quality.items():
        if q.delta is None:
            arrow = ""
        else:
            arrow = f" ▲ {q.delta:+.0%}" if q.delta >= 0 else f" ▼ {q.delta:+.0%}"
        st.progress(q.pass_rate, text=f"{dim}: {q.pass_rate:.0%}{arrow}")

with top_right.container(border=True):
    st.subheader("Severity")
    dots = {"P0": "🔴", "P1": "🟠", "P2": "🟡"}
    for sev, count in severities.items():
        if st.button(f"{dots[sev]} {sev}: {count} findings", key=f"sev_{sev}"):
            st.session_state["conv_severity_filter"] = sev
            st.switch_page("pages/conversations.py")

bottom_left, bottom_right = st.columns(2)

with bottom_left.container(border=True):
    st.subheader("Judge Accuracy")
    summary = metrics_run.summary if metrics_run else {}
    p, r = summary.get("precision"), summary.get("recall")
    st.metric("Precision (golden)", f"{p:.2f}" if p is not None else "—")
    st.metric("Recall (golden)", f"{r:.2f}" if r is not None else "—")
    agreement_text = f"{agreement.agreement:.0%}" if agreement.n_reviews else "—"
    st.metric("Human agreement", f"{agreement_text} ({agreement.n_reviews} reviews)")

with bottom_right.container(border=True):
    st.subheader("Top Clusters")
    if not top:
        st.caption("No clusters yet — run clustering from the Jobs page.")
    for card in top:
        label = f"{card.label} · {card.size} · {card.severity} · {card.routing}"
        if st.button(label, key=f"top_cluster_{card.cluster_id}"):
            st.session_state["clusters_filter_id"] = card.cluster_id
            st.switch_page("pages/clusters.py")

with st.container(border=True):
    st.caption(
        f"Total eval cost to date: {costs.total_eval_cents / 100:.2f} USD · "
        f"avg {costs.avg_per_call_cents:.2f}¢ per call"
    )
