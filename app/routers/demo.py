"""Demo UI support: the graph backbone, and a live stream of the agent's steps (Server-Sent Events).

Nothing in `app/agent/` changes: the stream runs the same LangGraph flow as POST /api/ask, step by step.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Security
from fastapi.responses import StreamingResponse
from neo4j import READ_ACCESS

from app.agent.graph import build_graph
from app.agent.llm import LLM, LLMUnavailable
from app.database.connection import get_driver
from app.dependencies import get_session
from app.models.agent import AskRequest
from app.routers.ask import llm_dependency
from app.security import require_api_key
from app.services.analytics.constants import SERIES_IDS

router = APIRouter(prefix="/api/demo", tags=["demo"])

MAX_TOUCHED = 80
MAX_STRINGS = 400

EVENT_RE = re.compile(r"^(GDELT|CB)-[\w-]+$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}")
CODE_RE = re.compile(r"^[A-Z][A-Z0-9_]{2,20}$")


def _key(var: str) -> str:
    """Cypher expression of a node's natural key (one per label, see docs/GRAPH_CONTRACT.md)."""
    return f"coalesce({var}.event_id, {var}.iso3, {var}.series_id, {var}.code, {var}.claim_id, toString({var}.date))"


def _id(var: str) -> str:
    """Cypher expression of the id used by the UI: `Label:key` (Country EUR and Currency EUR stay distinct)."""
    return f"labels({var})[0] + ':' + {_key(var)}"


def _node(var: str) -> str:
    """Cypher map describing one node for the UI."""
    return f"{{id: {_id(var)}, label: labels({var})[0], key: {_key(var)}, props: properties({var})}}"


def _edge(src: str, rel: str, dst: str) -> str:
    """Cypher map describing one relationship for the UI."""
    return f"{{source: {_id(src)}, target: {_id(dst)}, type: type({rel}), props: properties({rel})}}"


BACKBONE_NODES = f"// demo_backbone_nodes\nMATCH (n) WHERE NOT n:Event RETURN {_node('n')} AS node"
BACKBONE_EDGES = (
    "// demo_backbone_edges\nMATCH (a)-[r]->(b) WHERE NOT a:Event AND NOT b:Event "
    f"RETURN {_edge('a', 'r', 'b')} AS edge"
)
TOP_EVENTS = "// demo_top_events\nMATCH (e:Event) RETURN e.event_id AS id ORDER BY e.num_mentions DESC LIMIT $n"

# Events with their outgoing edges (country, theme, day, mentions), so a new event is drawn already connected.
EVENT_NEIGHBOURHOOD = f"""
// demo_event_neighbourhood
UNWIND $events AS k
MATCH (e:Event {{event_id: k}})
OPTIONAL MATCH (e)-[r]->(m)
RETURN {_node('e')} AS node, collect(CASE WHEN r IS NULL THEN null ELSE {_edge('e', 'r', 'm')} END) AS edges
"""

# Turns the strings found in a tool's arguments and result into graph nodes (one indexed lookup per label).
RESOLVE = f"""
// demo_resolve
CALL {{
  UNWIND $events AS k MATCH (n:Event {{event_id: k}}) RETURN n
  UNION
  UNWIND $days AS k MATCH (n:TradingDay {{date: date(k)}}) RETURN n
  UNION
  UNWIND $series AS k MATCH (n:PriceSeries {{series_id: k}}) RETURN n
  UNION
  UNWIND $codes AS k MATCH (n) WHERE (n:Theme OR n:Country OR n:Currency OR n:Commodity) AND (n.code = k OR n.iso3 = k)
  RETURN n
}}
RETURN elementId(n) AS eid, {_node('n')} AS node
LIMIT $limit
"""

# Edges between touched nodes: the hops the agent actually walked.
HOPS = f"""
// demo_hops
MATCH (a)-[r]->(b)
WHERE elementId(a) IN $eids AND elementId(b) IN $eids
RETURN {_edge('a', 'r', 'b')} AS edge
LIMIT 150
"""


@router.get("/graph")
def graph_backbone(
    session: Annotated[Any, Depends(get_session)],
    top_events: Annotated[int, Query(ge=0, le=500)] = 0,
) -> dict:
    """Every node except events (countries, themes, series, days...), plus the `top_events` most mentioned events."""
    nodes = [r["node"] for r in session.run(BACKBONE_NODES)]
    edges = [r["edge"] for r in session.run(BACKBONE_EDGES)]
    if top_events:
        ids = [r["id"] for r in session.run(TOP_EVENTS, n=top_events)]
        for row in session.run(EVENT_NEIGHBOURHOOD, events=ids):
            nodes.append(row["node"])
            edges.extend(e for e in row["edges"] if e)
    return json.loads(json.dumps({"nodes": nodes, "edges": edges}, default=str))


def collect_strings(value: Any, out: list[str]) -> list[str]:
    """Every string (and date) found in a nested tool argument or result, in order, at most MAX_STRINGS."""
    if len(out) >= MAX_STRINGS:
        return out
    if isinstance(value, dict):
        for item in value.values():
            collect_strings(item, out)
    elif isinstance(value, (list, tuple)):
        for item in value:
            collect_strings(item, out)
    elif value is not None and not isinstance(value, (int, float, bool)):
        out.append(str(value))
    return out


def classify(strings: list[str]) -> dict[str, list[str]]:
    """Sort candidate keys by the label they could belong to. Neo4j confirms which ones exist."""
    found: dict[str, set[str]] = {"events": set(), "days": set(), "series": set(), "codes": set()}
    for text in strings:
        text = text.strip()
        if EVENT_RE.match(text):
            found["events"].add(text)
        elif DATE_RE.match(text):
            found["days"].add(text[:10])
        elif text.upper() in SERIES_IDS:
            found["series"].add(text.upper())
        elif CODE_RE.match(text):
            found["codes"].add(text)
    return {kind: sorted(keys) for kind, keys in found.items()}


def touched_graph(session: Any, tool: str, arguments: dict, data: Any) -> dict:
    """Nodes touched by one tool call, the edges walked between them, and the edges that attach new events."""
    keys = classify(collect_strings([arguments, data], []))
    rows = list(session.run(RESOLVE, limit=MAX_TOUCHED, **keys))
    nodes = [r["node"] for r in rows]
    hops = [r["edge"] for r in session.run(HOPS, eids=[r["eid"] for r in rows])] if rows else []
    edges: list[dict] = []
    if keys["events"]:
        for row in session.run(EVENT_NEIGHBOURHOOD, events=keys["events"][:MAX_TOUCHED]):
            edges.extend(e for e in row["edges"] if e)
    if tool == "correlation":
        # The correlation is computed on the fly, not stored: draw it as a virtual Theme -> Series hop.
        for row in data or []:
            hops.append(
                {
                    "source": f"Theme:{row['theme']}",
                    "target": f"PriceSeries:{row['series_id']}",
                    "type": "CORRELATES_WITH",
                    "props": {"virtual": True, **{k: v for k, v in row.items() if k not in ("theme", "series_id")}},
                }
            )
    return {"nodes": nodes, "edges": edges, "hops": hops}


def sse(event: str, payload: Any) -> str:
    """One Server-Sent Event."""
    return f"event: {event}\ndata: {json.dumps(payload, default=str)}\n\n"


def summarise(data: Any) -> str:
    """One line about a tool result, for the step panel."""
    if isinstance(data, list):
        return f"{len(data)} rows"
    if isinstance(data, dict) and "candidates" in data:
        count = len(data["candidates"])
        return f"largest move {data.get('move_pct')}% on {data.get('move_day')}, {count} candidate events"
    return "result"


def agent_events(question: str, llm: LLM) -> Iterator[str]:
    """Run the agent graph and yield one SSE per step: start, plan, tool, validate, answer, done (or error)."""
    initial = {
        "question": question,
        "steps": 0,
        "tool_calls": [],
        "history": [],
        "paths": [],
        "cypher": [],
        "warnings": [],
        "hypothesis": False,
    }
    yield sse("start", {"question": question})
    try:
        with get_driver().session(default_access_mode=READ_ACCESS) as session:
            state = dict(initial)
            for update in build_graph(session, llm).stream(initial, stream_mode="updates"):
                for node, change in update.items():
                    change = change or {}
                    previous_cypher = len(state["cypher"])
                    state.update(change)
                    yield from _step_events(session, node, change, state, previous_cypher)
    except LLMUnavailable as exc:
        yield sse("error", {"detail": str(exc)})
    except Exception as exc:  # pylint: disable=broad-exception-caught
        # The stream has already started (HTTP 200): an error can only be reported as an event.
        yield sse("error", {"detail": f"{type(exc).__name__}: {str(exc)[:300]}"})
    yield sse("done", {})


def _step_events(session: Any, node: str, change: dict, state: dict, previous_cypher: int) -> Iterator[str]:
    """The SSE(s) for one finished LangGraph node."""
    if node == "parse_question":
        yield sse("parse", {"refused": change.get("refused", False), "warnings": change.get("warnings", [])})
    elif node == "plan":
        yield sse(
            "plan", {"step": state["steps"] + 1, **change["plan"].model_dump(), "warnings": change.get("warnings", [])}
        )
    elif node == "run_tools":
        last = state["history"][-1]
        call = state["tool_calls"][-1]
        data = last.get("result")
        payload = {
            "step": state["steps"],
            "tool": call.name,
            "arguments": call.arguments,
            "duration_ms": call.duration_ms,
            "ok": "result" in last,
            "error": last.get("error"),
            "summary": summarise(data) if "result" in last else "rejected",
            "cypher": state["cypher"][previous_cypher:],
            "result": data,
        }
        payload.update(
            touched_graph(session, call.name, call.arguments, data)
            if "result" in last
            else {"nodes": [], "edges": [], "hops": []}
        )
        yield sse("tool", payload)
    elif node == "validate":
        yield sse("validate", {"warnings": change.get("warnings", [])})
    elif node == "answer":
        yield sse("answer", change["answer"].model_dump())


@router.post("/ask/stream", dependencies=[Security(require_api_key)])
def ask_stream(body: AskRequest, llm: Annotated[LLM, Depends(llm_dependency)]) -> StreamingResponse:
    """Same agent as POST /api/ask, streamed step by step as Server-Sent Events for the demo UI."""
    return StreamingResponse(
        agent_events(body.question, llm),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
