"""Shared pytest fixtures."""

import pytest
from fastapi.testclient import TestClient

from app.database.connection import check_connection
from app.main import app


@pytest.fixture(name="client")
def client_fixture():
    """HTTP client bound to the FastAPI app (no network, no Neo4j needed)."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(name="neo4j_required")
def neo4j_required_fixture():
    """Skip the test when no Neo4j instance is reachable."""
    if not check_connection():
        pytest.skip("Neo4j is not reachable")
