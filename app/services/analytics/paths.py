"""Shortest paths in the graph: how two countries, or an event and a price series, are connected."""

from __future__ import annotations

from typing import Any

from app.services.analytics.constants import MAX_PATH_HOPS
from app.services.analytics.queries import clamp_limit, run_query

# The variable-length bound cannot be a Cypher parameter, so it is an int checked by `_hops` and injected.
PATHS_BETWEEN_COUNTRIES = """
// paths_between_countries
MATCH (a:Country {{iso3: $iso_a}}), (b:Country {{iso3: $iso_b}})
MATCH p = allShortestPaths((a)-[*1..{hops}]-(b))
RETURN [n IN nodes(p) | coalesce(n.iso3, n.event_id, toString(n.date), n.code)] AS nodes,
       [r IN relationships(p) | type(r)] AS relations, length(p) AS hops
LIMIT $limit
"""

PATHS_EVENT_TO_SERIES = """
// paths_event_to_series
MATCH (e:Event {{event_id: $event_id}}), (s:PriceSeries {{series_id: $series_id}})
MATCH p = allShortestPaths((e)-[*1..{hops}]-(s))
RETURN [n IN nodes(p) | coalesce(n.event_id, toString(n.date), n.series_id)] AS nodes,
       [r IN relationships(p) | type(r)] AS relations, length(p) AS hops
LIMIT $limit
"""


def _hops(max_hops: int) -> int:
    """Validate the path depth: an integer between 1 and MAX_PATH_HOPS."""
    value = int(max_hops)
    if not 1 <= value <= MAX_PATH_HOPS:
        raise ValueError(f"max_hops must be between 1 and {MAX_PATH_HOPS}")
    return value


def paths_between_countries(
    session: Any, iso_a: str, iso_b: str, max_hops: int = 4, limit: int | None = None
) -> list[dict]:
    """Shortest paths linking two countries through events and days."""
    query = PATHS_BETWEEN_COUNTRIES.format(hops=_hops(max_hops))
    return run_query(session, query, iso_a=iso_a.upper(), iso_b=iso_b.upper(), limit=clamp_limit(limit))


def paths_event_to_series(
    session: Any, event_id: str, series_id: str, max_hops: int = 3, limit: int | None = None
) -> list[dict]:
    """Shortest paths linking an event to a price series (through its day)."""
    query = PATHS_EVENT_TO_SERIES.format(hops=_hops(max_hops))
    return run_query(session, query, event_id=event_id, series_id=series_id.upper(), limit=clamp_limit(limit))
