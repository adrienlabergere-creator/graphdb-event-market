"""Analytical endpoints built on the analytics services (see docs/API_CONTRACT.md)."""

from typing import Annotated, Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query

from app.dependencies import get_session
from app.models.api import CentralityItem, CorrelationItem, ExplainMove, PathItem, TimelineItem
from app.routers.common import Page, paginate
from app.services import explain_move as explain_service
from app.services.analytics import gds, paths, queries
from app.services.analytics.constants import SERIES_IDS
from app.services.analytics.correlation import compute_theme_correlations

router = APIRouter(prefix="/api", tags=["analytics"])

Db = Annotated[object, Depends(get_session)]
Window = Annotated[int, Query(ge=30, le=365, description="Window in days")]


def _unknown(entity: str) -> HTTPException:
    """404 for an entity that is neither a series nor a theme."""
    return HTTPException(status_code=404, detail=f"Unknown entity: {entity}")


@router.get("/correlation/event-market", response_model=list[CorrelationItem])
def correlation(entity: str, session: Db, page: Page, window: Window = 90) -> list[CorrelationItem]:
    """Correlations between event themes and series, for a theme code or a series id (BRENT, VIX...)."""
    entity = entity.upper() if entity.upper() in SERIES_IDS else entity
    if entity not in SERIES_IDS and not explain_service.theme_exists(session, entity):
        raise _unknown(entity)
    items = []
    for series_id in [entity] if entity in SERIES_IDS else SERIES_IDS:
        end = explain_service.latest_day(session, series_id)
        if end is None:
            continue
        rows = compute_theme_correlations(session, series_id, explain_service.window_start(end, window), end)
        items += [r for r in rows if entity in (r["theme"], r["series_id"])]
    items.sort(key=lambda r: abs(r["corr"]), reverse=True)
    return paginate(
        [
            CorrelationItem(series=r["series_id"], **{k: r[k] for k in ("theme", "corr", "n", "lag_days")})
            for r in items
        ],
        page,
    )


@router.get("/explain/move", response_model=ExplainMove)
def explain_move(asset: str, session: Db, window: Window = 90) -> ExplainMove:
    """Largest move of an asset in the window and the events that preceded it (hypotheses)."""
    result = explain_service.explain_move(session, asset.upper(), window)
    if result is None:
        raise _unknown(asset)
    return ExplainMove(**result)


@router.get("/timeline/{asset}", response_model=list[TimelineItem])
def timeline(
    asset: str,
    session: Db,
    page: Page,
    start: Annotated[str, Query(alias="from", pattern=r"^\d{4}-\d{2}-\d{2}$")],
    end: Annotated[str, Query(alias="to", pattern=r"^\d{4}-\d{2}-\d{2}$")],
) -> list[TimelineItem]:
    """Day by day: events of the day and the price move of the asset."""
    if asset.upper() not in SERIES_IDS:
        raise _unknown(asset)
    rows = queries.timeline(session, asset.upper(), start, end)
    return paginate([TimelineItem(**row) for row in rows], page)


@router.get("/events/{event_id}/paths", response_model=list[PathItem])
def event_paths(
    event_id: str, to_series: str, session: Db, page: Page, max_depth: Annotated[int, Query(ge=1, le=6)] = 4
) -> list[PathItem]:
    """Shortest paths between an event and a series."""
    rows = paths.paths_event_to_series(session, event_id, to_series, max_hops=max_depth, limit=page.limit)
    if not rows:
        raise HTTPException(status_code=404, detail="No path found (unknown event or series)")
    return [PathItem(nodes=[str(n) for n in r["nodes"]], relations=r["relations"], hops=r["hops"]) for r in rows]


@router.get("/graph/centrality", response_model=list[CentralityItem])
def centrality(
    session: Db,
    metric: Literal["pagerank"] = "pagerank",  # pylint: disable=unused-argument
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
):
    """Countries ranked by PageRank (Graph Data Science)."""
    # One projection name per request: two concurrent calls would otherwise drop each other's graph.
    name = f"{gds.GRAPH_NAME}-{uuid4().hex[:8]}"
    gds.project_graph(session, name)
    try:
        return [CentralityItem(**row) for row in gds.page_rank(session, name, limit=limit)]
    finally:
        gds.drop_graph(session, name)
