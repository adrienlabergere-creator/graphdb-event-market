"""Tests of the demo UI endpoints: graph backbone and the streamed agent steps (no Neo4j, no model)."""

import json
from contextlib import contextmanager

import pytest
from fakes import FakeLLM, FakeSession

from app.config import Settings, get_settings
from app.dependencies import get_session
from app.main import app
from app.models.agent import Plan
from app.routers import demo
from app.routers.ask import llm_dependency

API_KEY = {"X-API-Key": "test-key"}
NODE = {"id": "PriceSeries:VIX", "label": "PriceSeries", "key": "VIX", "props": {"series_id": "VIX"}}
EDGE = {"source": "PriceSeries:VIX", "target": "TradingDay:2026-06-02", "type": "PRICE_ON", "props": {}}
EVENT = {"id": "Event:GDELT-1", "label": "Event", "key": "GDELT-1", "props": {"date": "2026-06-02"}}
ROWS = {
    "demo_backbone_nodes": [{"node": NODE}],
    "demo_backbone_edges": [{"edge": EDGE}],
    "demo_top_events": [{"id": "GDELT-1"}],
    "demo_event_neighbourhood": [{"node": EVENT, "edges": [None]}],
}


class FakeDriver:
    """Stands in for the Neo4j driver used by the stream."""

    def __init__(self, session):
        self.fake_session = session

    @contextmanager
    def session(self, **_):
        """Yield the fake session."""
        yield self.fake_session


def events_of(response) -> list[tuple[str, dict]]:
    """Parse a Server-Sent Events body into (event, data) pairs."""
    pairs = []
    for block in response.text.strip().split("\n\n"):
        lines = dict(line.split(": ", 1) for line in block.split("\n"))
        pairs.append((lines["event"], json.loads(lines["data"])))
    return pairs


@pytest.fixture(name="demo_api")
def demo_api_fixture(client, monkeypatch):
    """Test client with a fake session, a known API key and a scripted model (set by each test)."""
    session = FakeSession(ROWS)
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_settings] = lambda: Settings(_env_file=None, api_key="test-key")
    monkeypatch.setattr(demo, "get_driver", lambda: FakeDriver(session))
    yield client
    app.dependency_overrides.clear()


def test_classify_sorts_candidate_keys():
    """Event ids, dates, series and codes are told apart; plain words are ignored."""
    keys = demo.classify(["GDELT-12", "2026-06-02T00:00", "vix", "CAMEO_19", "IRN", "a fight"])
    assert keys == {
        "events": ["GDELT-12"],
        "days": ["2026-06-02"],
        "series": ["VIX"],
        "codes": ["CAMEO_19", "IRN"],
        "names": [],
    }


def test_cypher_literals_light_up_what_a_count_query_filters_on():
    """A query that only returns a count still names its country and dates in its quoted values."""
    cypher = "MATCH (e:Event)-[:OCCURRED_IN]->(c:Country) WHERE c.name = 'Iran' AND e.date >= date(\"2026-03-01\") RETURN count(e)"
    literals = demo.cypher_literals({"cypher": cypher})
    assert literals == ["Iran", "2026-03-01"]
    assert demo.classify(literals, keep_names=True)["names"] == ["Iran"]
    assert demo.classify(literals, keep_names=True)["days"] == ["2026-03-01"]


def test_collect_strings_walks_nested_results():
    """Strings are collected from dicts and lists; numbers and booleans are skipped."""
    found = demo.collect_strings([{"series_id": "VIX"}, {"rows": [{"day": "2026-06-02", "n": 3, "ok": True}]}], [])
    assert found == ["VIX", "2026-06-02"]


def test_backbone_returns_nodes_edges_and_top_events(demo_api):
    """GET /api/demo/graph is public and adds the requested top events."""
    body = demo_api.get("/api/demo/graph", params={"top_events": 1}).json()
    assert [n["id"] for n in body["nodes"]] == ["PriceSeries:VIX", "Event:GDELT-1"]
    assert body["edges"] == [EDGE]


def test_stream_needs_the_api_key(demo_api):
    """The stream is protected like POST /api/ask."""
    app.dependency_overrides[llm_dependency] = FakeLLM
    assert demo_api.post("/api/demo/ask/stream", json={"question": "Why did the VIX move?"}).status_code == 401


def test_stream_refuses_financial_advice(demo_api):
    """A request for advice is refused at parse time: no plan, no tool."""
    app.dependency_overrides[llm_dependency] = FakeLLM
    response = demo_api.post("/api/demo/ask/stream", json={"question": "Should I buy oil now?"}, headers=API_KEY)
    assert response.headers["content-type"].startswith("text/event-stream")
    names = [name for name, _ in events_of(response)]
    assert names == ["start", "parse", "answer", "done"]
    assert events_of(response)[1][1]["refused"] is True


def test_stream_reports_a_blocked_write_query(demo_api):
    """A write query planned by the model is shown as a blocked tool step, then the run ends normally."""
    llm = FakeLLM(plans=[Plan(tool="graph_query", arguments={"cypher": "MATCH (e:Event) DELETE e"})])
    app.dependency_overrides[llm_dependency] = lambda: llm
    response = demo_api.post("/api/demo/ask/stream", json={"question": "Delete all the events"}, headers=API_KEY)
    pairs = events_of(response)
    assert [name for name, _ in pairs] == ["start", "parse", "plan", "tool", "plan", "validate", "answer", "done"]
    tool = pairs[3][1]
    assert tool["ok"] is False and "DELETE" in tool["error"]
    assert tool["nodes"] == [] and tool["hops"] == []
