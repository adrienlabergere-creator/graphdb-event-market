"""Container health checks against the running Docker Compose stack (skipped when it is not up)."""

import os

import httpx
import pytest

PROXY_URL = os.getenv("API_BASE_URL", "http://localhost:8080")
NEO4J_HTTP_URL = os.getenv("NEO4J_HTTP_URL", "http://localhost:7474")


def _is_up(url: str) -> bool:
    """Return True if the URL answers within two seconds."""
    try:
        return httpx.get(url, timeout=2).status_code < 500
    except httpx.HTTPError:
        return False


@pytest.mark.integration
def test_api_healthy_through_reverse_proxy():
    """FastAPI answers /health through the Nginx reverse proxy."""
    if not _is_up(f"{PROXY_URL}/health"):
        pytest.skip("Docker Compose stack is not running")
    response = httpx.get(f"{PROXY_URL}/health", timeout=5)
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.integration
def test_neo4j_container_healthy():
    """The Neo4j HTTP endpoint answers."""
    if not _is_up(NEO4J_HTTP_URL):
        pytest.skip("Docker Compose stack is not running")
    assert httpx.get(NEO4J_HTTP_URL, timeout=5).status_code == 200
