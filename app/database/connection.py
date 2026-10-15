"""Neo4j driver management."""

from functools import lru_cache

from neo4j import Driver, GraphDatabase
from neo4j.exceptions import DriverError, Neo4jError

from app.config import get_settings


@lru_cache
def get_driver() -> Driver:
    """Return a shared Neo4j driver (created lazily, no connection is opened yet)."""
    settings = get_settings()
    return GraphDatabase.driver(settings.neo4j_uri, auth=(settings.neo4j_user, settings.neo4j_password))


def check_connection() -> bool:
    """Return True if Neo4j answers a trivial query, False otherwise."""
    try:
        with get_driver().session() as session:
            record = session.run("RETURN 1 AS ok").single()
            return record is not None and record["ok"] == 1
    except (DriverError, Neo4jError, OSError):
        return False
