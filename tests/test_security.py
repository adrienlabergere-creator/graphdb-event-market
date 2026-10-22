"""Tests of the API key on POST /api/ask: accepted, missing, wrong, unset on the server, and Swagger."""

import pytest
from fakes import FakeLLM, FakeSession

from app.config import Settings, get_settings
from app.dependencies import get_session
from app.main import app
from app.routers.ask import llm_dependency

QUESTION = {"question": "Why did Brent move?"}


def settings_with_key(key: str):
    """A settings factory for dependency_overrides, with the given API_KEY and no .env file."""
    return lambda: Settings(_env_file=None, api_key=key)


@pytest.fixture(name="secured")
def secured_fixture(client):
    """The test client with a fake session, a scripted model and API_KEY=secret on the server."""
    app.dependency_overrides[get_session] = lambda: FakeSession()
    app.dependency_overrides[llm_dependency] = lambda: FakeLLM()
    app.dependency_overrides[get_settings] = settings_with_key("secret")
    yield client
    app.dependency_overrides.clear()


def test_right_key_is_accepted(secured):
    """The agent answers when X-API-Key matches API_KEY."""
    response = secured.post("/api/ask", json=QUESTION, headers={"X-API-Key": "secret"})
    assert response.status_code == 200
    assert "answer" in response.json()


def test_missing_key_is_a_401(secured):
    """Without the header the request is refused with a readable message."""
    response = secured.post("/api/ask", json=QUESTION)
    assert response.status_code == 401
    assert "X-API-Key" in response.json()["detail"]
    assert response.headers["WWW-Authenticate"] == "APIKey"


@pytest.mark.parametrize("key", ["wrong", "secre", "secret ", "sécret".encode()])
def test_wrong_key_is_a_401(secured, key):
    """A wrong, truncated, padded or non-ASCII key is refused (and never crashes the comparison)."""
    response = secured.post("/api/ask", json=QUESTION, headers={"X-API-Key": key})
    assert response.status_code == 401


def test_no_key_configured_on_the_server_fails_closed(secured):
    """If API_KEY is empty the endpoint is closed (503), even for a client that sends a key."""
    app.dependency_overrides[get_settings] = settings_with_key("")
    for headers in ({}, {"X-API-Key": ""}, {"X-API-Key": "anything"}):
        response = secured.post("/api/ask", json=QUESTION, headers=headers)
        assert response.status_code == 503
        assert "API key not configured" in response.json()["detail"]


def test_key_is_checked_before_neo4j_and_the_model(client):
    """A request without a key is refused before a Neo4j session or the model is created."""
    app.dependency_overrides[get_settings] = settings_with_key("secret")
    try:
        response = client.post("/api/ask", json=QUESTION)
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 401


def test_read_only_endpoints_stay_public(client):
    """GET endpoints do not need the key."""
    app.dependency_overrides[get_settings] = settings_with_key("secret")
    try:
        assert client.get("/health").status_code == 200
    finally:
        app.dependency_overrides.clear()


def test_swagger_declares_the_key_on_the_agent_only(client):
    """OpenAPI declares the X-API-Key scheme (Authorize button) and requires it only on the two agent endpoints."""
    schema = client.get("/openapi.json").json()
    scheme = schema["components"]["securitySchemes"]["APIKeyHeader"]
    assert scheme == {**scheme, "type": "apiKey", "in": "header", "name": "X-API-Key"}
    secured = [
        (path, method)
        for path, operations in schema["paths"].items()
        for method, operation in operations.items()
        if operation.get("security")
    ]
    assert sorted(secured) == [("/api/ask", "post"), ("/api/demo/ask/stream", "post")]
