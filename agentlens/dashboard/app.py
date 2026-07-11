"""AgentLens dashboard shell: role selector, role-filtered nav, status block.

Run with: uv run streamlit run agentlens/dashboard/app.py
"""

import streamlit as st

from agentlens.dashboard.data import status_summary
from agentlens.dashboard.ui import inject_css
from agentlens.db import open_session

# Page registry: title -> (file, roles that see it in the nav). Call Detail is
# routable but never a nav item (reached via row clicks), per the UI design.
_PAGE_FILES: dict[str, str] = {
    "Overview": "pages/overview.py",
    "Conversations": "pages/conversations.py",
    "Clusters": "pages/clusters.py",
    "Review Queue": "pages/review_queue.py",
    "Fix Workbench": "pages/fix_workbench.py",
    "Jobs": "pages/jobs.py",
    "Call Detail": "pages/call_detail.py",
}

PAGES_BY_ROLE: dict[str, list[str]] = {
    "Engineer": ["Overview", "Conversations", "Clusters", "Fix Workbench", "Jobs"],
    "Reviewer": ["Overview", "Review Queue"],
    "Lead": ["Overview", "Conversations", "Clusters"],
}


def main() -> None:
    """Render the shell and dispatch to the current page."""
    st.set_page_config(page_title="AgentLens", layout="wide")
    inject_css()

    pages = {title: st.Page(path, title=title) for title, path in _PAGE_FILES.items()}
    current = st.navigation(list(pages.values()), position="hidden")

    with st.sidebar:
        st.title("AgentLens")
        role = st.selectbox("Role", ["Engineer", "Reviewer", "Lead"], key="role")
        st.divider()
        for title in PAGES_BY_ROLE[role]:
            st.page_link(pages[title], label=title)
        st.divider()
        with open_session() as session:
            summary = status_summary(session)
        last_eval = (
            summary.last_eval_at.strftime("%Y-%m-%d %H:%M") if summary.last_eval_at else "never"
        )
        st.caption(
            f"Last eval run: {last_eval}\n\n"
            f"Corpus calls: {summary.n_calls}\n\n"
            f"Golden calls: {summary.n_golden}"
        )

    current.run()


main()
