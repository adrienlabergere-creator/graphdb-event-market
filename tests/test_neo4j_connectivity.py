"""Neo4j connectivity tests (skipped when no database is reachable)."""

import pytest

from app.database.connection import get_driver


@pytest.mark.neo4j
def test_neo4j_answers_simple_query(neo4j_required):
    """The driver can run a trivial query against the database."""
    with get_driver().session() as session:
        assert session.run("RETURN 1 AS n").single()["n"] == 1
