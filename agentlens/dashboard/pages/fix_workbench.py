"""Fix Workbench page (Engineer): propose a fix, run regression, review the delta.

The Generate Fix and Apply & Run Regression buttons spend real LLM budget when
clicked; both go through the gateway and are logged in llm_call_log.
"""

import pandas as pd
import streamlit as st

from agentlens.dashboard.data import cluster_cards, latest_fix, latest_regression
from agentlens.db import open_session
from agentlens.evals.runner import evaluate_call
from agentlens.fixes.propose import propose_fix
from agentlens.fixes.regression import regenerate_for_fix
from agentlens.fixes.report import build_regression_run
from agentlens.models import Cluster, FixProposal

st.header("Fix Workbench")

with open_session() as session:
    selectable = [c for c in cluster_cards(session) if not c.is_p0]
    if not selectable:
        st.info("No non-P0 clusters available — run clustering from the Jobs page.")
        st.stop()

    by_label = {c.label: c.cluster_id for c in selectable}
    preset_id = st.session_state.pop("fix_cluster_id", None)
    preset_label = next((label for label, cid in by_label.items() if cid == preset_id), None)
    labels = list(by_label)
    cluster_label = st.selectbox(
        "Cluster",
        labels,
        index=labels.index(preset_label) if preset_label is not None else 0,
    )
    cluster_id = by_label[cluster_label]
    cluster = session.get(Cluster, cluster_id)
    assert cluster is not None  # id came from the query above
    is_p0 = cluster.dominant_severity == "P0"

    fix = latest_fix(session, cluster_id)

    with st.container(border=True):
        st.subheader("Proposed Fix")
        if st.button("Generate Fix"):
            result = propose_fix(session, cluster)
            if result.success and result.parsed is not None:
                fix = FixProposal(
                    cluster_id=cluster.id,
                    fix_type=result.parsed.fix_type,
                    rationale=result.parsed.rationale,
                    patch=result.parsed.patch,
                )
                session.add(fix)
                session.commit()
                st.rerun()
            else:
                st.error(f"Fix generation failed: {result.error}")
        if fix is None:
            st.caption("No fix proposed yet.")
        else:
            st.markdown(f"**Type:** {fix.fix_type} · **Status:** {fix.status}")
            st.write(fix.rationale)
            st.code(fix.patch)
            if st.button(
                "Apply & Run Regression",
                disabled=is_p0,
                help=(
                    "P0 findings require human acknowledgment before regression can run"
                    if is_p0
                    else None
                ),
            ):
                with st.spinner("Regenerating affected scenarios and re-running evals…"):
                    regenerated = regenerate_for_fix(session, fix)
                    for call in regenerated:
                        evaluate_call(session, call)
                    build_regression_run(session, fix, regenerated)
                    session.commit()
                st.rerun()

    run = latest_regression(session, fix.id) if fix is not None else None
    if run is not None:
        with st.container(border=True):
            st.subheader("Regression Results")
            dims = sorted(set(run.before_pass_rates) | set(run.after_pass_rates))
            rows = []
            worst_drop = 0.0
            for dim in dims:
                before = run.before_pass_rates.get(dim)
                after = run.after_pass_rates.get(dim)
                delta = after - before if before is not None and after is not None else None
                if delta is not None and delta < 0:
                    worst_drop = min(worst_drop, delta)
                if delta is None:
                    delta_text, status = "—", ""
                elif delta > 0:
                    delta_text, status = f"▲ {delta:+.0%}", ""
                elif delta < 0:
                    delta_text, status = f"▼ {delta:+.0%}", "⚠"
                else:
                    delta_text, status = "—", ""
                rows.append(
                    {
                        "Dimension": dim,
                        "Before": f"{before:.0%}" if before is not None else "—",
                        "After": f"{after:.0%}" if after is not None else "—",
                        "Delta": delta_text,
                        "Status": status,
                    }
                )
            if worst_drop < -0.05:
                st.warning(f"A dimension regressed by more than 5pp ({worst_drop:+.0%}).")
            st.dataframe(pd.DataFrame(rows), hide_index=True)
            st.caption(
                f"target: {run.target_dimension} · regenerated batch: {run.batch_id} · "
                f"n_before {run.n_before} · n_after {run.n_after}"
            )
