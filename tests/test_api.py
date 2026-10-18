"""Tests of the analytical endpoints and POST /api/ask with a fake session (no Neo4j, no model)."""

import pytest
from fakes import MOVE_ROWS, FakeLLM, FakeSession, series_rows
from neo4j.exceptions import ServiceUnavailable

from app.config import Settings, get_settings
from app.dependencies import get_session
from app.main import app
from app.routers.ask import llm_dependency

EVENTS = [{"theme": "CAMEO_19", "day": r["day"], "n": i % 7} for i, r in enumerate(series_rows(60))]
ROWS = {
    **MOVE_ROWS,
    "events_per_day_by_theme": EVENTS,
    "returns": series_rows(60),
    "theme_exists": [{"n": 1}],
    "pagerank": [
        {"iso3": "UKR", "country": "Ukraine", "score": 0.4},
        {"iso3": "RUS", "country": "Russia", "score": 0.3},
    ],
}


API_KEY = {"X-API-Key": "test-key"}


def keyed_settings() -> Settings:
    """Settings with a known API key, independent of the local .env."""
    return Settings(_env_file=None, api_key="test-key")


@pytest.fixture(name="api")
def api_fixture(client):
    """The test client with a fake Neo4j session, a scripted model and a known API key."""
    app.dependency_overrides[get_session] = lambda: FakeSession(ROWS)
    app.dependency_overrides[get_settings] = keyed_settings
    app.dependency_overrides[llm_dependency] = lambda: FakeLLM()
    yield client
    app.dependency_overrides.clear()


def test_openapi_lists_every_endpoint(api):
    """Swagger documents the 5 analytical endpoints and /api/ask."""
    paths = api.get("/openapi.json").json()["paths"]
    for path in (
        "/api/correlation/event-market",
        "/api/explain/move",
        "/api/timeline/{asset}",
        "/api/events/{event_id}/paths",
        "/api/graph/centrality",
        "/api/ask",
    ):
        assert path in paths
    assert api.get("/docs").status_code == 200


def test_correlation_for_a_series_is_sorted_paginated_and_a_hypothesis(api):
    """Each item has status hypothesis and a disclaimer; limit and offset are applied."""
    response = api.get("/api/correlation/event-market", params={"entity": "brent", "limit": 2})
    items = response.json()
    assert response.status_code == 200 and len(items) == 2
    assert all(i["series"] == "BRENT" and i["status"] == "hypothesis" and i["disclaimer"] for i in items)
    assert abs(items[0]["corr"]) >= abs(items[1]["corr"])
    assert api.get("/api/correlation/event-market", params={"entity": "BRENT", "offset": 99}).json() == []


def test_correlation_for_a_theme_and_unknown_entity(api):
    """A theme code works; an unknown code is a 404."""
    assert api.get("/api/correlation/event-market", params={"entity": "CAMEO_19"}).status_code == 200
    app.dependency_overrides[get_session] = lambda: FakeSession({"theme_exists": [{"n": 0}]})
    assert api.get("/api/correlation/event-market", params={"entity": "NOPE"}).status_code == 404


def test_pagination_limits_are_validated(api):
    """limit above 100 is a 422."""
    assert api.get("/api/correlation/event-market", params={"entity": "BRENT", "limit": 101}).status_code == 422


def test_explain_move_returns_candidates_with_paths(api):
    """The largest move and its candidate events, each with a graph path."""
    body = api.get("/api/explain/move", params={"asset": "brent"}).json()
    assert body["asset"] == "BRENT" and body["move_pct"] == 5.0 and body["status"] == "hypothesis"
    assert body["candidates"][0]["score"] == 1.0 and body["candidates"][0]["path"][-1] == "BRENT"


def test_explain_move_unknown_asset_is_404(api):
    """A series without data is a 404."""
    app.dependency_overrides[get_session] = lambda: FakeSession()
    assert api.get("/api/explain/move", params={"asset": "GOLD"}).status_code == 404


def test_timeline(api):
    """The `from` and `to` parameters are read and an unknown asset is a 404."""
    ok = api.get("/api/timeline/BRENT", params={"from": "2026-07-01", "to": "2026-07-31"})
    assert ok.status_code == 200 and ok.json()[1]["ret_1d"] == 0.05
    assert api.get("/api/timeline/GOLD", params={"from": "2026-07-01", "to": "2026-07-31"}).status_code == 404
    assert api.get("/api/timeline/BRENT", params={"from": "July", "to": "2026-07-31"}).status_code == 422


def test_event_paths(api):
    """Paths are returned; no path is a 404; a depth above 6 is a 422."""
    ok = api.get("/api/events/GDELT-1/paths", params={"to_series": "BRENT"})
    assert ok.json()[0]["hops"] == 2
    assert api.get("/api/events/GDELT-1/paths", params={"to_series": "BRENT", "max_depth": 7}).status_code == 422
    app.dependency_overrides[get_session] = lambda: FakeSession()
    assert api.get("/api/events/NOPE/paths", params={"to_series": "BRENT"}).status_code == 404


def test_centrality_ranks_countries(api):
    """PageRank ranking of countries."""
    body = api.get("/api/graph/centrality", params={"limit": 2}).json()
    assert [row["iso3"] for row in body] == ["UKR", "RUS"]


def test_neo4j_down_is_a_503(api):
    """A database failure becomes HTTP 503 with a readable message."""
    app.dependency_overrides[get_session] = lambda: FakeSession(error=ServiceUnavailable("down"))
    response = api.get("/api/explain/move", params={"asset": "BRENT"})
    assert response.status_code == 503 and "Neo4j" in response.json()["detail"]


def test_ask_returns_a_structured_answer(api):
    """POST /api/ask returns the AgentAnswer fields."""
    body = api.post("/api/ask", json={"question": "Why did Brent move?"}, headers=API_KEY).json()
    assert {
        "answer",
        "status",
        "confidence",
        "tool_calls",
        "graph_paths",
        "cypher_used",
        "warnings",
        "disclaimer",
    } <= set(body)


def test_ask_validates_the_question(api):
    """An empty or too short question is a 422."""
    assert api.post("/api/ask", json={"question": ""}, headers=API_KEY).status_code == 422


def test_ask_without_a_configured_model_is_a_503(client, monkeypatch):
    """When LLM_MODEL is not set the endpoint answers 503, not a crash."""
    monkeypatch.setattr("app.agent.llm.get_settings", lambda: type("S", (), {"llm_model": "", "ollama_base_url": ""})())
    app.dependency_overrides[get_session] = lambda: FakeSession()
    app.dependency_overrides[get_settings] = keyed_settings
    response = client.post("/api/ask", json={"question": "Why did Brent move?"}, headers=API_KEY)
    app.dependency_overrides.clear()
    assert response.status_code == 503 and "LLM_MODEL" in response.json()["detail"]
