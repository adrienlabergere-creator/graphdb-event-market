"""Candidate events for the largest move of a series in a window (a hypothesis, never a proven cause)."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from app.services.analytics.paths import paths_event_to_series
from app.services.analytics.queries import events_before_moves, run_query, timeline

LATEST_DAY = """
// latest_day
MATCH (:PriceSeries {series_id: $series_id})-[p:PRICE_ON]->(d:TradingDay)
WHERE p.ret_1d IS NOT NULL
RETURN toString(max(d.date)) AS day
"""

THEME_EXISTS = """
// theme_exists
MATCH (t:Theme {code: $code})
RETURN count(t) AS n
"""


def latest_day(session: Any, series_id: str) -> str | None:
    """Last day with a price return for the series, or None when the series is unknown or empty."""
    rows = run_query(session, LATEST_DAY, series_id=series_id)
    return rows[0]["day"] if rows else None


def theme_exists(session: Any, code: str) -> bool:
    """True when a Theme node has this code."""
    return run_query(session, THEME_EXISTS, code=code)[0]["n"] > 0


def window_start(end: str, window: int) -> str:
    """First day of a window of `window` days ending on `end`."""
    return (date.fromisoformat(end) - timedelta(days=window)).isoformat()


def explain_move(session: Any, series_id: str, window: int = 90, limit: int = 5) -> dict | None:
    """Largest daily move of the series in the window and the events of the 1 to 3 days before it.

    Returns None when the series has no data. The score is the share of mentions of the most mentioned candidate.
    """
    end = latest_day(session, series_id)
    if end is None:
        return None
    start = window_start(end, window)
    days = [row for row in timeline(session, series_id, start, end) if row["ret_1d"] is not None]
    if not days:
        return None
    biggest = max(days, key=lambda row: abs(row["ret_1d"]))
    events = events_before_moves(session, series_id, start, end, max_lag=3, top_moves=1, limit=limit)
    top = max((e["mentions"] for e in events), default=0) or 1
    candidates = []
    for event in events:
        found = paths_event_to_series(session, event["event_id"], series_id, max_hops=3, limit=1)
        candidates.append(
            {
                "event_id": event["event_id"],
                "title": event["title"],
                "score": round(event["mentions"] / top, 3),
                "path": found[0]["nodes"] if found else [],
            }
        )
    return {
        "asset": series_id,
        "move_pct": round(biggest["ret_1d"] * 100, 3),
        "move_day": biggest["day"],
        "candidates": candidates,
    }
