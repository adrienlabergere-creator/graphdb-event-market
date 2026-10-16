"""Graph Data Science: projection, PageRank (influence) and Louvain (communities).

Needs the GDS plugin (the Docker image of the project loads it). The projection is in memory and is dropped after use.
"""

from __future__ import annotations

from typing import Any

from app.services.analytics.constants import GRAPH_NAME
from app.services.analytics.queries import clamp_limit, run_query

NODE_LABELS = ["Event", "Country", "Theme", "TradingDay", "PriceSeries"]
RELATIONSHIPS = {
    "OCCURRED_IN": {"orientation": "UNDIRECTED"},
    "HAS_THEME": {"orientation": "UNDIRECTED"},
    "ON_DAY": {"orientation": "UNDIRECTED"},
    "PRICE_ON": {"orientation": "UNDIRECTED"},
}

DROP_GRAPH = "CALL gds.graph.drop($name, false) YIELD graphName RETURN graphName"
PROJECT_GRAPH = """
CALL gds.graph.project($name, $labels, $relationships)
YIELD graphName, nodeCount, relationshipCount
RETURN graphName, nodeCount, relationshipCount
"""

PAGERANK = """
// pagerank
CALL gds.pageRank.stream($name)
YIELD nodeId, score
WITH gds.util.asNode(nodeId) AS n, score
WHERE 'Country' IN labels(n)
RETURN n.iso3 AS iso3, n.name AS country, score
ORDER BY score DESC
LIMIT $limit
"""

LOUVAIN = """
// louvain
CALL gds.louvain.stream($name)
YIELD nodeId, communityId
WITH gds.util.asNode(nodeId) AS n, communityId
WHERE 'Country' IN labels(n)
RETURN communityId AS community, collect(n.iso3) AS countries
ORDER BY size(countries) DESC
LIMIT $limit
"""


def project_graph(session: Any, name: str = GRAPH_NAME) -> dict:
    """(Re)create the in-memory projection and return its size."""
    run_query(session, DROP_GRAPH, name=name)
    rows = run_query(session, PROJECT_GRAPH, name=name, labels=NODE_LABELS, relationships=RELATIONSHIPS)
    return rows[0] if rows else {}


def page_rank(session: Any, name: str = GRAPH_NAME, limit: int | None = None) -> list[dict]:
    """Countries ranked by PageRank on the projected graph."""
    return run_query(session, PAGERANK, name=name, limit=clamp_limit(limit))


def communities(session: Any, name: str = GRAPH_NAME, limit: int | None = None) -> list[dict]:
    """Louvain communities of countries on the projected graph."""
    return run_query(session, LOUVAIN, name=name, limit=clamp_limit(limit))


def drop_graph(session: Any, name: str = GRAPH_NAME) -> None:
    """Free the projection."""
    run_query(session, DROP_GRAPH, name=name)


def run_gds(session: Any, limit: int | None = None) -> dict:
    """Project, run both algorithms, drop the projection and return everything."""
    info = project_graph(session)
    try:
        return {
            "projection": info,
            "pagerank": page_rank(session, limit=limit),
            "communities": communities(session, limit=limit),
        }
    finally:
        drop_graph(session)
