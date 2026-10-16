"""Correlation between daily event counts (per theme) and daily returns of a price series.

The result is a descriptive statistic stored on `(:Theme)-[:CORRELATES_WITH]->(:PriceSeries)`. It never states a cause.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import numpy as np

from app.services.analytics.constants import CORRELATION_LAGS, MIN_SAMPLES
from app.services.analytics.queries import EVENTS_PER_DAY_BY_THEME, RETURNS, run_query

STORE_CORRELATION = """
MATCH (t:Theme {code: $theme}), (s:PriceSeries {series_id: $series_id})
MERGE (t)-[c:CORRELATES_WITH {lag_days: $lag_days}]->(s)
SET c.corr = $corr, c.window_days = $window_days, c.n = $n, c.computed_at = datetime()
"""


def pearson(x: list[float], y: list[float]) -> float | None:
    """Pearson correlation of two equal-length series, or None when it is undefined (too short, constant)."""
    if len(x) != len(y) or len(x) < 3:
        return None
    a, b = np.asarray(x, dtype=float), np.asarray(y, dtype=float)
    if a.std() == 0 or b.std() == 0:
        return None
    return float(np.corrcoef(a, b)[0, 1])


def aligned_samples(
    counts: dict[str, int], returns: list[tuple[str, float]], lag_days: int
) -> tuple[list[float], list[float]]:
    """Pair each return with the event count `lag_days` calendar days earlier (0 when no event that day)."""
    xs, ys = [], []
    for day, ret in returns:
        earlier = (date.fromisoformat(day) - timedelta(days=lag_days)).isoformat()
        xs.append(float(counts.get(earlier, 0)))
        ys.append(ret)
    return xs, ys


def correlations_for_theme(
    counts: dict[str, int],
    returns: list[tuple[str, float]],
    lags: tuple[int, ...] = CORRELATION_LAGS,
    min_samples: int = MIN_SAMPLES,
) -> list[dict]:
    """One row per lag: correlation of the theme's daily event count with the return `lag` days later."""
    rows = []
    for lag in lags:
        xs, ys = aligned_samples(counts, returns, lag)
        value = pearson(xs, ys) if len(xs) >= min_samples else None
        if value is not None:
            rows.append({"lag_days": lag, "corr": round(value, 4), "n": len(xs)})
    return rows


def compute_theme_correlations(
    session: Any, series_id: str, start: str, end: str, lags: tuple[int, ...] = CORRELATION_LAGS
) -> list[dict]:
    """Correlations of every theme with one series for several lags, sorted by absolute value."""
    events = run_query(session, EVENTS_PER_DAY_BY_THEME, start=start, end=end, margin=max(lags))
    returns = [
        (row["day"], row["ret"]) for row in run_query(session, RETURNS, series_id=series_id, start=start, end=end)
    ]
    by_theme: dict[str, dict[str, int]] = {}
    for row in events:
        by_theme.setdefault(row["theme"], {})[row["day"]] = row["n"]
    result = []
    for theme, counts in by_theme.items():
        for item in correlations_for_theme(counts, returns, lags):
            result.append({"theme": theme, "series_id": series_id, **item})
    return sorted(result, key=lambda r: abs(r["corr"]), reverse=True)


def window_days(start: str, end: str) -> int:
    """Length of the analysed window in calendar days."""
    return (date.fromisoformat(end) - date.fromisoformat(start)).days + 1


def store_correlations(session: Any, rows: list[dict], start: str, end: str) -> int:
    """Write the correlations as CORRELATES_WITH relationships (idempotent per theme, series and lag)."""
    size = window_days(start, end)
    for row in rows:
        session.run(
            STORE_CORRELATION,
            theme=row["theme"],
            series_id=row["series_id"],
            lag_days=row["lag_days"],
            corr=row["corr"],
            n=row["n"],
            window_days=size,
        )
    return len(rows)
