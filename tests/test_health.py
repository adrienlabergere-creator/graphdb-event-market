"""Tests for the health endpoints and the OpenAPI documentation."""

from app.routers import health as health_router


def test_health_ok(client):
    """The liveness probe answers without touching Neo4j."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "neo4j": None}


def test_health_db_unreachable_returns_503(client, monkeypatch):
    """When Neo4j is down the readiness probe returns a meaningful 503."""
    monkeypatch.setattr(health_router, "check_connection", lambda: False)
    response = client.get("/health/db")
    assert response.status_code == 503
    assert "Neo4j" in response.json()["detail"]


def test_health_db_ok(client, monkeypatch):
    """When Neo4j answers the readiness probe reports it."""
    monkeypatch.setattr(health_router, "check_connection", lambda: True)
    response = client.get("/health/db")
    assert response.status_code == 200
    assert response.json()["neo4j"] is True


def test_swagger_docs_available(client):
    """Swagger UI is served at /docs."""
    assert client.get("/docs").status_code == 200


def test_openapi_lists_health_routes(client):
    """The OpenAPI schema exposes the health routes."""
    paths = client.get("/openapi.json").json()["paths"]
    assert "/health" in paths
    assert "/health/db" in paths
