"""Load daily market series from FRED into Neo4j (idempotent: MERGE everywhere).

Usage:
    python -m scripts.ingest_prices --start 2026-01-01 --end 2026-07-31

Each FRED series becomes a (:PriceSeries) linked to a (:Commodity) or (:Currency) it tracks (rates track nothing),
and one (:PriceSeries)-[:PRICE_ON {close, ret_1d}]->(:TradingDay) per observation.
No API key is needed for the CSV endpoint.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass

from app.database.connection import get_driver
from scripts.ingest_common import RAW_DIR, download, run_batches

FRED_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={fred_id}&cosd={start}&coed={end}"


@dataclass(frozen=True)
class SeriesSpec:
    """Description of one FRED series."""

    series_id: str  # our identifier
    fred_id: str
    name: str
    unit: str
    kind: str  # commodity, fx or rate
    target: tuple[str, str, str] | None = None  # (label Commodity or Currency, code, name)


SERIES: list[SeriesSpec] = [
    SeriesSpec(
        "BRENT",
        "DCOILBRENTEU",
        "Brent crude oil",
        "USD per barrel",
        "commodity",
        ("Commodity", "BRENT", "Brent crude oil"),
    ),
    SeriesSpec(
        "WTI", "DCOILWTICO", "WTI crude oil", "USD per barrel", "commodity", ("Commodity", "WTI", "WTI crude oil")
    ),
    SeriesSpec("EURUSD", "DEXUSEU", "USD per euro", "USD per EUR", "fx", ("Currency", "EUR", "Euro")),
    SeriesSpec("USDJPY", "DEXJPUS", "JPY per USD", "JPY per USD", "fx", ("Currency", "JPY", "Japanese yen")),
    SeriesSpec("US10Y", "DGS10", "US Treasury 10-year yield", "percent", "rate"),
]

UPSERT_SERIES = """
MERGE (s:PriceSeries {series_id: $series_id})
SET s.source = 'FRED', s.ticker = $fred_id, s.name = $name, s.unit = $unit, s.kind = $kind
"""

LINK_TARGET = """
MATCH (s:PriceSeries {series_id: $series_id})
MERGE (x:%s {code: $code})
ON CREATE SET x.name = $target_name
MERGE (s)-[:TRACKS]->(x)
"""

UPSERT_PRICES = """
UNWIND $rows AS r
MATCH (s:PriceSeries {series_id: $series_id})
MERGE (d:TradingDay {date: date(r.date)})
SET d.is_trading_day = true
MERGE (s)-[p:PRICE_ON]->(d)
SET p.close = r.close, p.ret_1d = r.ret_1d
"""


def parse_fred_csv(text: str) -> list[tuple[str, float]]:
    """Parse a FRED CSV (header, then `date,value` lines). Missing values ('.' or empty) are skipped."""
    points = []
    for line in text.strip().splitlines()[1:]:
        parts = line.strip().split(",")
        if len(parts) < 2 or parts[1] in (".", ""):
            continue
        try:
            points.append((parts[0], float(parts[1])))
        except ValueError:
            continue
    return points


def compute_returns(points: list[tuple[str, float]], kind: str) -> list[dict]:
    """Rows with close and ret_1d. ret_1d is a simple return, except for rates: change in percentage points."""
    rows, previous = [], None
    for day, close in points:
        if previous is None:
            ret = None
        elif kind == "rate":
            ret = close - previous
        else:
            ret = close / previous - 1 if previous else None
        rows.append({"date": day, "close": close, "ret_1d": ret})
        previous = close
    return rows


def fetch_series(spec: SeriesSpec, start: str, end: str) -> list[tuple[str, float]]:
    """Download (or read from the local cache) one FRED series."""
    target = RAW_DIR / "fred" / f"{spec.fred_id}_{start}_{end}.csv"
    download(FRED_URL.format(fred_id=spec.fred_id, start=start, end=end), target)
    return parse_fred_csv(target.read_text(encoding="utf-8"))


def load_series(session, spec: SeriesSpec, points: list[tuple[str, float]]) -> int:
    """Write one series and its prices. Returns the number of price points."""
    session.run(
        UPSERT_SERIES, series_id=spec.series_id, fred_id=spec.fred_id, name=spec.name, unit=spec.unit, kind=spec.kind
    ).consume()
    if spec.target:
        label, code, target_name = spec.target
        session.run(LINK_TARGET % label, series_id=spec.series_id, code=code, target_name=target_name).consume()
    return run_batches(session, UPSERT_PRICES, compute_returns(points, spec.kind), series_id=spec.series_id)


def main() -> None:
    """Command-line entry point."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--start", default="2026-01-01")
    parser.add_argument("--end", default="2026-07-31")
    args = parser.parse_args()
    with get_driver().session() as session:
        for spec in SERIES:
            count = load_series(session, spec, fetch_series(spec, args.start, args.end))
            print(f"{spec.series_id}: {count} price points")


if __name__ == "__main__":
    main()
