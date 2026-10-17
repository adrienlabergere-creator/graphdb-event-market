"""FastAPI dependencies: a read-only Neo4j session per request."""

from collections.abc import Iterator

from neo4j import READ_ACCESS, Session

from app.database.connection import get_driver


def get_session() -> Iterator[Session]:
    """Open a read-only Neo4j session for the duration of one request."""
    with get_driver().session(default_access_mode=READ_ACCESS) as session:
        yield session
