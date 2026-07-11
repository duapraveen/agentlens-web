"""Shared dashboard rendering helpers: CSS, badges, dimension dots."""

import streamlit as st

from agentlens.corpus.scenarios import Dimension

DIMENSION_ORDER = [d.value for d in Dimension]

_CSS = """
<style>
div[data-testid="stVerticalBlock"] div.p0-card {
    border-left: 4px solid #d33;
    padding-left: 0.6rem;
}
</style>
"""


def inject_css() -> None:
    """Inject the app-wide custom CSS (P0 row/card borders)."""
    st.markdown(_CSS, unsafe_allow_html=True)


def dimension_dots(failed: set[str]) -> str:
    """Four-dot indicator in fixed dimension order: ● failed, ○ passed."""
    return "".join("●" if dim in failed else "○" for dim in DIMENSION_ORDER)


def severity_badge(severity: str) -> str:
    """Compact severity marker for headers and tables."""
    return {"P0": "⚠ P0", "P1": "P1", "P2": "P2"}.get(severity, "✓")
