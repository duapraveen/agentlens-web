"""Clusters page (Engineer, Lead): recurring failure patterns; entry to the fix loop."""

import streamlit as st

from agentlens.dashboard.data import cluster_cards, last_job_run
from agentlens.dashboard.ui import severity_badge
from agentlens.db import open_session

st.header("Clusters")

focus_id = st.session_state.get("clusters_filter_id")
if focus_id is not None and st.button("Show all clusters"):
    del st.session_state["clusters_filter_id"]
    st.rerun()

with open_session() as session:
    f1, f2 = st.columns(2)
    routing = f1.selectbox(
        "Routing", ["All", "prompt_fix", "retrieval_data_fix", "ops_process", "model_config"]
    )
    severity = f2.selectbox("Severity", ["All", "P0", "P1", "P2"])

    cards = cluster_cards(
        session,
        routing=None if routing == "All" else routing,
        severity=None if severity == "All" else severity,
    )
    if focus_id is not None:
        cards = [c for c in cards if c.cluster_id == focus_id]

    last_run = last_job_run(session, "recluster")
    clustered_at = (
        last_run.finished_at.strftime("%H:%M") if last_run and last_run.finished_at else "never"
    )
    n_failures = sum(c.size for c in cards)
    st.caption(f"{len(cards)} clusters · {n_failures} failures · last clustered {clustered_at}")

for card in cards:
    with st.container(border=True):
        if card.is_p0:
            st.markdown('<div class="p0-card"></div>', unsafe_allow_html=True)
        st.subheader(f"{severity_badge(card.severity)} {card.label} · {card.size} calls")
        st.caption(f"routing: {card.routing} · dominant severity: {card.severity}")
        st.write(card.description)
        act1, act2 = st.columns([1, 1])
        if act1.button(f"View {card.size} calls", key=f"view_{card.cluster_id}"):
            st.session_state["conversations_cluster_id"] = card.cluster_id
            st.switch_page("pages/conversations.py")
        if act2.button(
            "Propose Fix",
            key=f"fix_{card.cluster_id}",
            disabled=card.is_p0,
            help=(
                "P0 findings require human resolution before a fix can be proposed"
                if card.is_p0
                else None
            ),
        ):
            st.session_state["fix_cluster_id"] = card.cluster_id
            st.switch_page("pages/fix_workbench.py")
