"""Shell tests: role table, shared UI helpers, and an AppTest smoke run."""

from pathlib import Path

import pytest
from sqlalchemy import create_engine
from streamlit.testing.v1 import AppTest

from agentlens.dashboard.app import PAGES_BY_ROLE
from agentlens.dashboard.ui import dimension_dots, severity_badge
from agentlens.models import Base

_APP = "agentlens/dashboard/app.py"


@pytest.fixture()
def dash_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> str:
    url = f"sqlite:///{tmp_path}/dash.db"
    Base.metadata.create_all(create_engine(url))
    monkeypatch.setenv("AGENTLENS_DATABASE_URL", url)
    monkeypatch.setenv("AGENTLENS_JOBS_LOG_PATH", str(tmp_path / "logs" / "jobs.log"))
    return url


def test_role_table_matches_design() -> None:
    assert set(PAGES_BY_ROLE) == {"Engineer", "Reviewer", "Lead"}
    assert PAGES_BY_ROLE["Engineer"] == [
        "Overview",
        "Conversations",
        "Clusters",
        "Fix Workbench",
        "Jobs",
    ]
    assert PAGES_BY_ROLE["Reviewer"] == ["Overview", "Review Queue"]
    assert PAGES_BY_ROLE["Lead"] == ["Overview", "Conversations", "Clusters"]


def test_dimension_dots_fixed_order() -> None:
    assert dimension_dots(set()) == "○○○○"
    assert dimension_dots({"task_completion", "safety_compliance"}) == "●○●○"


def test_severity_badge() -> None:
    assert "P0" in severity_badge("P0")
    assert severity_badge("none") == "✓"


def test_shell_renders_with_role_selector(dash_env: str) -> None:
    at = AppTest.from_file(_APP, default_timeout=10)
    at.run()
    assert not at.exception
    role = at.sidebar.selectbox[0]
    assert role.options == ["Engineer", "Reviewer", "Lead"]


def test_role_switch_reruns_clean(dash_env: str) -> None:
    at = AppTest.from_file(_APP, default_timeout=10)
    at.run()
    at.sidebar.selectbox[0].select("Reviewer").run()
    assert not at.exception
    assert at.session_state["role"] == "Reviewer"
