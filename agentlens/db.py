"""Engine and session helpers. All DB access goes through the ORM (no raw SQL)."""

from pathlib import Path

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session

from agentlens.config import get_settings
from agentlens.models import Base


def create_db_engine(url: str | None = None) -> Engine:
    """Create an engine for `url` (default: settings) and ensure the schema exists."""
    resolved = url or get_settings().database_url
    if resolved.startswith("sqlite:///"):
        db_path = Path(resolved.removeprefix("sqlite:///"))
        db_path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(resolved)
    Base.metadata.create_all(engine)
    return engine


def open_session(url: str | None = None) -> Session:
    """A new Session bound to a fresh engine. Use as a context manager."""
    return Session(create_db_engine(url))
