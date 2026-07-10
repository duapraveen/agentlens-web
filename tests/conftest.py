"""Shared test fixtures."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from agentlens.models import Base


@pytest.fixture()
def db_session(tmp_path: Path) -> Iterator[Session]:
    """A Session bound to a fresh file-backed SQLite database in tmp_path."""
    engine = create_engine(f"sqlite:///{tmp_path}/test.db")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
