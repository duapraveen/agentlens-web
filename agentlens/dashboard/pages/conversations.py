"""Conversations page (Engineer, Lead): browse evaluated calls, drill into one."""

from typing import Literal

import pandas as pd
import streamlit as st

from agentlens.dashboard.data import conversation_rows
from agentlens.dashboard.ui import DIMENSION_ORDER, dimension_dots
from agentlens.db import open_session
from agentlens.models import Cluster

_PAGE_SIZE = 25
_OUTCOMES: dict[str, Literal["pass", "fail"]] = {"Pass only": "pass", "Fail only": "fail"}

st.header("Conversations")

with open_session() as session:
    clusters = session.query(Cluster).order_by(Cluster.label).all()
    cluster_by_label = {c.label: c.id for c in clusters}

    preset_cluster_id = st.session_state.pop("conversations_cluster_id", None)
    if preset_cluster_id is not None:
        preset_label = next(
            (label for label, cid in cluster_by_label.items() if cid == preset_cluster_id), None
        )
        if preset_label is not None:
            st.session_state["conv_cluster_filter"] = preset_label

    f1, f2, f3, f4 = st.columns([2, 2, 2, 2])
    severity = f1.selectbox("Severity", ["All", "P0", "P1", "P2"], key="conv_severity_filter")
    dimension = f2.selectbox("Dimension", ["All", *DIMENSION_ORDER])
    cluster_label = f3.selectbox("Cluster", ["All", *cluster_by_label], key="conv_cluster_filter")
    outcome_label = f4.selectbox("Outcome", ["All", "Pass only", "Fail only"])

    rows = conversation_rows(
        session,
        severity=None if severity == "All" else severity,
        dimension=None if dimension == "All" else dimension,
        cluster_id=None if cluster_label == "All" else cluster_by_label[cluster_label],
        outcome=_OUTCOMES.get(outcome_label),
    )

n_failed = sum(1 for r in rows if r.failed_dimensions)
n_p0 = sum(1 for r in rows if r.has_p0)
st.caption(f"{len(rows)} calls · {n_failed} with failures · {n_p0} P0")

page = st.session_state.setdefault("conversations_page", 0)
page = max(0, min(page, (len(rows) - 1) // _PAGE_SIZE if rows else 0))
visible = rows[page * _PAGE_SIZE : (page + 1) * _PAGE_SIZE]

table = pd.DataFrame(
    [
        {
            "ID": r.call_id,
            "Scenario": r.scenario,
            "Fails": dimension_dots(r.failed_dimensions),
            "P0": "⚠" if r.has_p0 else "",
            "Avg Score": round(r.avg_score, 1),
            "Cost (est ¢)": round(r.est_cost_cents, 2),
            "Date": r.created_at.strftime("%Y-%m-%d %H:%M"),
        }
        for r in visible
    ]
)
selection = st.dataframe(
    table,
    hide_index=True,
    on_select="rerun",
    selection_mode="single-row",
    key="conversations_table",
)

prev_col, page_col, next_col = st.columns([1, 2, 1])
if prev_col.button("← Prev", disabled=page == 0):
    st.session_state["conversations_page"] = page - 1
    st.rerun()
page_col.caption(f"Page {page + 1} of {max(1, -(-len(rows) // _PAGE_SIZE))}")
if next_col.button("Next →", disabled=(page + 1) * _PAGE_SIZE >= len(rows)):
    st.session_state["conversations_page"] = page + 1
    st.rerun()

selected = selection.get("selection", {}).get("rows", [])
if selected:
    st.session_state["selected_call_id"] = visible[selected[0]].call_id
    st.session_state["call_detail_origin"] = "pages/conversations.py"
    st.switch_page("pages/call_detail.py")
