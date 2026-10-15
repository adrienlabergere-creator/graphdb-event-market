"""Parameterised Cypher queries and the Python functions that run them.

Every query is read-only, takes its values as parameters (never string-formatted) and ends with a LIMIT or an
aggregation that is bounded by the number of days or themes. Each template starts with a `// name` comment so the
benchmark script and the logs can name it.
"""

from __future__ import annotations

from typing import Any

from app.services.analytics.constants import DEFAULT_LIMIT, MAX_LIMIT

TOP_COUNTRIES = """
// top_countries
MATCH (e:Event)-[:OCCURRED_IN]->(c:Country)
WHERE e.date >= date($start) AND e.date <= date($end)
RETURN c.iso3 AS iso3, c.name AS country, count(e) AS events, avg(e.goldstein) AS avg_goldstein,
       sum(e.num_mentions) AS mentions
ORDER BY events DESC
LIMIT $limit
"""

TOP_EVENTS = """
// top_events
MATCH (e:Event)-[:OCCURRED_IN]->(c:Country)
MATCH (e)-[:HAS_THEME]->(t:Theme)
WHERE e.date >= date($start) AND e.date <= date($end)
RETURN e.event_id AS event_id, toString(e.date) AS day, e.title AS title, c.iso3 AS iso3, t.label AS theme,
       e.num_mentions AS mentions, e.goldstein AS goldstein
ORDER BY e.num_mentions DESC
LIMIT $limit
"""

TIMELINE = """
// timeline
MATCH (d:TradingDay)
WHERE d.date >= date($start) AND d.date <= date($end)
OPTIONAL MATCH (:PriceSeries {series_id: $series_id})-[p:PRICE_ON]->(d)
RETURN toString(d.date) AS day, d.event_count AS events, p.close AS close, p.ret_1d AS ret_1d
ORDER BY d.date
LIMIT $limit
"""

EVENTS_BEFORE_MOVES = """
// events_before_moves
MATCH (:PriceSeries {series_id: $series_id})-[p:PRICE_ON]->(d:TradingDay)
WHERE d.date >= date($start) AND d.date <= date($end) AND p.ret_1d IS NOT NULL
WITH d, p.ret_1d AS move
ORDER BY abs(move) DESC
LIMIT $top_moves
UNWIND range(1, $max_lag) AS lag
MATCH (prev:TradingDay {date: d.date - duration({days: lag})})<-[:ON_DAY]-(e:Event)-[:HAS_THEME]->(t:Theme)
WHERE $theme IS NULL OR t.code = $theme
RETURN e.event_id AS event_id, e.title AS title, t.code AS theme, toString(prev.date) AS event_day,
       toString(d.date) AS move_day, lag AS lag_days, move, e.num_mentions AS mentions
ORDER BY e.num_mentions DESC
LIMIT $limit
"""

THEME_IMPACT = """
// theme_impact
MATCH (:PriceSeries {series_id: $series_id})-[p:PRICE_ON]->(d:TradingDay)
WHERE d.date >= date($start) AND d.date <= date($end) AND p.ret_1d IS NOT NULL
WITH d, abs(p.ret_1d) AS move
OPTIONAL MATCH (:TradingDay {date: d.date - duration({days: 1})})<-[:ON_DAY]-(e:Event)-[:HAS_THEME]->(t:Theme)
WITH t, d, move, count(e) AS n
WHERE t IS NOT NULL
RETURN t.code AS theme, count(d) AS days, avg(move) AS avg_abs_move, avg(n) AS avg_events_day_before
ORDER BY avg_abs_move DESC
LIMIT $limit
"""

EVENTS_PER_DAY_BY_THEME = """
// events_per_day_by_theme
MATCH (e:Event)-[:HAS_THEME]->(t:Theme)
MATCH (e)-[:ON_DAY]->(d:TradingDay)
WHERE d.date >= date($start) - duration({days: $margin}) AND d.date <= date($end)
RETURN t.code AS theme, toString(d.date) AS day, count(e) AS n
"""

RETURNS = """
// returns
MATCH (:PriceSeries {series_id: $series_id})-[p:PRICE_ON]->(d:TradingDay)
WHERE d.date >= date($start) AND d.date <= date($end) AND p.ret_1d IS NOT NULL
RETURN toString(d.date) AS day, p.ret_1d AS ret
ORDER BY d.date
"""

# Queries listed by the benchmark script with the parameters used to run them.
BENCHMARK_QUERIES = {
    "top_countries": TOP_COUNTRIES,
    "top_events": TOP_EVENTS,
    "timeline": TIMELINE,
    "events_before_moves": EVENTS_BEFORE_MOVES,
    "theme_impact": THEME_IMPACT,
}


def clamp_limit(limit: int | None) -> int:
    """Return a LIMIT between 1 and MAX_LIMIT (the default when `limit` is None)."""
    if limit is None:
        return DEFAULT_LIMIT
    return max(1, min(int(limit), MAX_LIMIT))


def run_query(session: Any, query: str, **params: Any) -> list[dict]:
    """Run a query and return its rows as plain dictionaries."""
    return [dict(record) for record in session.run(query, **params)]


def top_countries(session: Any, start: str, end: str, limit: int | None = None) -> list[dict]:
    """Countries with the most events in the window, with their average Goldstein score."""
    return run_query(session, TOP_COUNTRIES, start=start, end=end, limit=clamp_limit(limit))


def top_events(session: Any, start: str, end: str, limit: int | None = None) -> list[dict]:
    """Most mentioned events of the window, with country and theme."""
    return run_query(session, TOP_EVENTS, start=start, end=end, limit=clamp_limit(limit))


def timeline(session: Any, series_id: str, start: str, end: str, limit: int = MAX_LIMIT) -> list[dict]:
    """Day by day: number of events, close and daily return of one series."""
    return run_query(session, TIMELINE, series_id=series_id, start=start, end=end, limit=clamp_limit(limit))


def events_before_moves(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    session: Any,
    series_id: str,
    start: str,
    end: str,
    *,
    max_lag: int = 3,
    top_moves: int = 10,
    theme: str | None = None,
    limit: int | None = None,
) -> list[dict]:
    """Events that happened 1 to `max_lag` days before the `top_moves` largest daily moves of a series.

    This lists co-occurrences in time. It does not say that an event caused a move.
    """
    return run_query(
        session,
        EVENTS_BEFORE_MOVES,
        series_id=series_id,
        start=start,
        end=end,
        max_lag=max(1, min(int(max_lag), 7)),
        top_moves=max(1, min(int(top_moves), 50)),
        theme=theme,
        limit=clamp_limit(limit),
    )


def theme_impact(session: Any, series_id: str, start: str, end: str, limit: int | None = None) -> list[dict]:
    """Average absolute daily move of a series, by the theme of the events of the day before."""
    return run_query(session, THEME_IMPACT, series_id=series_id, start=start, end=end, limit=clamp_limit(limit))
