"""Shared FastAPI test fixtures: an isolated DB session wired into the app."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from agentlens.api.deps import get_db
from agentlens.api.main import app
from agentlens.models import Base


@pytest.fixture()
def db_session(tmp_path: Path) -> Iterator[Session]:
    """A Session bound to a fresh file-backed SQLite database in tmp_path."""
    engine = create_engine(f"sqlite:///{tmp_path}/test.db")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture()
def client(db_session: Session) -> Iterator[TestClient]:
    """A TestClient whose get_db dependency is overridden to use db_session."""

    def _override() -> Iterator[Session]:
        yield db_session

    app.dependency_overrides[get_db] = _override
    yield TestClient(app)
    app.dependency_overrides.clear()
