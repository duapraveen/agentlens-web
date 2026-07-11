"""Call Detail page: full diagnostic view of one evaluated call (AC-3.1, AC-3.2)."""

import streamlit as st

from agentlens.dashboard.data import call_detail
from agentlens.dashboard.ui import severity_badge
from agentlens.db import open_session

call_id = st.session_state.get("selected_call_id")
origin = st.session_state.get("call_detail_origin", "pages/conversations.py")

if call_id is None:
    st.info("Select a call from Conversations or the Review Queue.")
    st.stop()

with open_session() as session:
    detail = call_detail(session, call_id)
    if detail is None:
        st.error(f"Call `{call_id}` not found.")
        st.stop()

    top_left, top_right = st.columns([1, 3])
    if top_left.button("← Back"):
        st.switch_page(origin)
    header = f"Call {detail.call.id} · {detail.call.scenario}"
    if detail.cluster is not None:
        top_right.caption(f"Cluster: {detail.cluster.label}")
        if top_right.button(f"View cluster → {detail.cluster.label}"):
            st.session_state["clusters_filter_id"] = detail.cluster.id
            st.switch_page("pages/clusters.py")
    st.header(header)

    st.subheader("Transcript")
    with st.container(height=300):
        for turn in detail.call.transcript:
            speaker = str(turn.get("speaker", "")).capitalize()
            st.markdown(f"**{speaker}:** {turn.get('text', '')}")

    st.subheader("Scores")
    check_lines = [
        f"⚠ {c.check_name.upper()}" if c.triggered else f"✓ {c.check_name}" for c in detail.checks
    ]
    for record in detail.records:
        status = "pass" if record.passed else "FAIL"
        title = (
            f"{record.dimension} · {record.score} · {severity_badge(record.severity)} · "
            f"{status} · stage: {record.pipeline_stage or '—'}"
        )
        with st.expander(title):
            st.write(record.judge_reasoning)
            if record.failure_description:
                st.markdown(f"**Finding:** {record.failure_description}")
            st.markdown("**Deterministic checks:**")
            st.text("\n".join(check_lines) if check_lines else "✓ No deterministic flags")
            st.caption(
                f"Prompt v{record.prompt_version} · Model: {record.judge_model} · "
                f"Rubric v{record.rubric_version} · Input hash: {record.input_hash}"
            )

    is_engineer = st.session_state.get("role", "Engineer") == "Engineer"
    if is_engineer and st.toggle("Show ground truth"):
        gt = detail.ground_truth
        if gt is None:
            st.info("No injected failure — this is a clean call.")
        else:
            st.warning(
                f"Injected: {gt.failure_mode} · stage: {gt.pipeline_stage} · "
                f"severity: {gt.severity}"
            )
