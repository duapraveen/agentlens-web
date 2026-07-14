"""FastAPI dependency providing a DB session per request."""

from collections.abc import Iterator

from sqlalchemy.orm import Session

from agentlens.db import open_session


def get_db() -> Iterator[Session]:
    """Yield a session for the request lifetime, closing it afterward."""
    session = open_session()
    try:
        yield session
    finally:
        session.close()
