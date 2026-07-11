"""Review Queue page (Reviewer): confirm or reject judge findings, one at a time."""

import streamlit as st

from agentlens.db import open_session
from agentlens.feedback.calibration import compute_agreement
from agentlens.feedback.queue import review_queue, submit_review

st.header("Review Queue")

with open_session() as session:
    stats = compute_agreement(session)
    queue = review_queue(session)
    pending = [r for r in queue if r.review is None]

    with st.container(border=True):
        col1, col2, col3 = st.columns(3)
        col1.metric("Agreement", f"{stats.agreement:.0%}" if stats.n_reviews else "—")
        col2.metric("Reviews", stats.n_reviews)
        col3.metric("Pending", len(pending))
        if stats.per_dimension:
            st.caption(
                " · ".join(
                    f"{dim}: {rate:.0%} ({stats.per_dimension_counts[dim]})"
                    for dim, rate in sorted(stats.per_dimension.items())
                )
            )

    if not pending:
        st.success("Queue clear — every flagged finding has a verdict.")
        st.stop()

    finding = pending[0]
    call = finding.call
    with st.container(border=True):
        st.subheader(f"{call.id} · {call.scenario}")
        st.markdown(f"**{finding.dimension}** · score {finding.score} · {finding.severity}")
        st.write(finding.failure_description or "(no description)")
        checks = call.check_results
        check_text = (
            "\n".join(
                f"⚠ {c.check_name.upper()}" if c.triggered else f"✓ {c.check_name}" for c in checks
            )
            if checks
            else "✓ No deterministic flags"
        )
        st.text(check_text)
        with st.expander("View full transcript"):
            for turn in call.transcript:
                speaker = str(turn.get("speaker", "")).capitalize()
                st.markdown(f"**{speaker}:** {turn.get('text', '')}")

    verdict = st.radio("Verdict", ["Agree", "Disagree"], index=None, horizontal=True)
    note = st.text_area("Note (optional)")
    if st.button("Submit & Next", disabled=verdict is None) and verdict is not None:
        submit_review(session, finding.id, verdict.lower(), note or None)  # type: ignore[arg-type]
        session.commit()
        st.rerun()
