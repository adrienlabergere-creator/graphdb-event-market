"""The four tools of the agent. Each one returns a ToolResult and never raises on bad arguments."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from neo4j import Query
from pydantic import BaseModel, Field, ValidationError

from app.agent.guardrails import QUERY_TIMEOUT_S, GuardrailError, validate_cypher
from app.services import explain_move as explain_service
from app.services.analytics.constants import SERIES_IDS
from app.services.analytics.correlation import compute_theme_correlations
from app.services.analytics.queries import timeline

DATE = r"^\d{4}-\d{2}-\d{2}$"


@dataclass
class ToolResult:
    """What a tool returns: data for the LLM, graph paths and Cypher used for the answer."""

    data: Any
    paths: list[list[str]] = field(default_factory=list)
    cypher: list[str] = field(default_factory=list)
    hypothesis: bool = True


class GraphQueryArgs(BaseModel):
    """Arguments of `graph_query`."""

    cypher: str = Field(min_length=5, max_length=1500)


class CorrelationArgs(BaseModel):
    """Arguments of `correlation`."""

    series_id: str
    theme: str | None = None
    window: int = Field(default=90, ge=30, le=365)


class TimelineArgs(BaseModel):
    """Arguments of `timeline`."""

    series_id: str
    start: str = Field(pattern=DATE)
    end: str = Field(pattern=DATE)


class ExplainMoveArgs(BaseModel):
    """Arguments of `explain_move`."""

    series_id: str
    window: int = Field(default=90, ge=30, le=365)


def _series(series_id: str) -> str:
    """Normalise and check a series id."""
    series_id = series_id.upper()
    if series_id not in SERIES_IDS:
        raise ValueError(f"Unknown series {series_id}. Known: {', '.join(SERIES_IDS)}")
    return series_id


def graph_query(session: Any, arguments: dict) -> ToolResult:
    """Run a read-only Cypher query after the guardrails (allow-list, schema, depth, LIMIT, timeout)."""
    args = GraphQueryArgs(**arguments)
    query = validate_cypher(args.cypher)
    rows = [dict(record) for record in session.run(Query(query, timeout=QUERY_TIMEOUT_S))]
    return ToolResult(data=rows[:50], cypher=[query], hypothesis=False)


def correlation(session: Any, arguments: dict) -> ToolResult:
    """Correlations between event themes and a series."""
    args = CorrelationArgs(**arguments)
    series_id = _series(args.series_id)
    end = explain_service.latest_day(session, series_id)
    rows = (
        compute_theme_correlations(session, series_id, explain_service.window_start(end, args.window), end)
        if end
        else []
    )
    if args.theme:
        rows = [r for r in rows if r["theme"] == args.theme]
    return ToolResult(data=rows[:10])


def timeline_tool(session: Any, arguments: dict) -> ToolResult:
    """Events per day and price moves of a series between two dates."""
    args = TimelineArgs(**arguments)
    return ToolResult(data=timeline(session, _series(args.series_id), args.start, args.end, limit=60))


def explain_move(session: Any, arguments: dict) -> ToolResult:
    """Candidate events (and their graph paths) for the largest move of a series."""
    args = ExplainMoveArgs(**arguments)
    result = explain_service.explain_move(session, _series(args.series_id), args.window)
    if result is None:
        return ToolResult(data={"error": "no data for this series"})
    return ToolResult(data=result, paths=[c["path"] for c in result["candidates"] if c["path"]])


TOOLS = {
    "graph_query": graph_query,
    "correlation": correlation,
    "timeline": timeline_tool,
    "explain_move": explain_move,
}

TOOL_DESCRIPTIONS = {
    "graph_query": 'arguments {"cypher": "<read-only Cypher>"}. Facts from the graph (counts, lists).',
    "correlation": 'arguments {"series_id": "BRENT", "theme": "CAMEO_19" (optional), "window": 90}.',
    "timeline": 'arguments {"series_id": "VIX", "start": "2026-03-01", "end": "2026-03-31"}.',
    "explain_move": 'arguments {"series_id": "US10Y", "window": 90}. Largest move and the events before it.',
}

TOOL_ERRORS = (ValidationError, GuardrailError, ValueError)
