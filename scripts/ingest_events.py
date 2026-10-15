"""Load events into Neo4j (idempotent: MERGE everywhere).

Two sources, both reproducible from public data:
  * geopolitical tension events from the GDELT 1.0 daily event files (CAMEO root codes 13 to 19);
  * central-bank decisions derived from FRED policy-rate series (every change of the rate is an event).

Usage:
    python -m scripts.ingest_events --start 2026-02-01 --end 2026-07-31 --step 1 --top 25
    python -m scripts.ingest_events --skip-gdelt          # central-bank events only

`--step N` keeps one day out of N (the daily GDELT files are large). `--top` keeps the N most mentioned events per day.
"""

from __future__ import annotations

import argparse
import csv
import io
import zipfile
from collections import defaultdict
from datetime import date

from app.database.connection import get_driver
from scripts.ingest_common import RAW_DIR, days_between, download, parse_day, run_batches
from scripts.ingest_prices import FRED_URL, parse_fred_csv

GDELT_URL = "http://data.gdeltproject.org/events/{day}.export.CSV.zip"

# Column positions in a GDELT 1.0 event row (tab separated, 58 columns).
COL_ID, COL_DATE, COL_ACTOR1, COL_ACTOR2 = 0, 1, 6, 16
COL_EVENT_CODE, COL_ROOT_CODE, COL_GOLDSTEIN, COL_MENTIONS, COL_TONE = 26, 28, 30, 31, 34
COL_GEO_NAME, COL_GEO_COUNTRY, COL_URL = 50, 51, 57
MIN_COLUMNS = 58

# GDELT uses FIPS 10-4 country codes; we store ISO 3166 alpha-3.
FIPS_TO_ISO3 = {
    "US": ("USA", "United States"),
    "CH": ("CHN", "China"),
    "RS": ("RUS", "Russia"),
    "UP": ("UKR", "Ukraine"),
    "GM": ("DEU", "Germany"),
    "UK": ("GBR", "United Kingdom"),
    "JA": ("JPN", "Japan"),
    "IR": ("IRN", "Iran"),
    "IS": ("ISR", "Israel"),
    "SA": ("SAU", "Saudi Arabia"),
    "FR": ("FRA", "France"),
    "IN": ("IND", "India"),
    "TU": ("TUR", "Turkey"),
    "BR": ("BRA", "Brazil"),
    "MX": ("MEX", "Mexico"),
    "CA": ("CAN", "Canada"),
    "KS": ("KOR", "South Korea"),
    "TW": ("TWN", "Taiwan"),
    "IZ": ("IRQ", "Iraq"),
    "SY": ("SYR", "Syria"),
    "VE": ("VEN", "Venezuela"),
    "NI": ("NGA", "Nigeria"),
    "SF": ("ZAF", "South Africa"),
    "AS": ("AUS", "Australia"),
    "LE": ("LBN", "Lebanon"),
    "YM": ("YEM", "Yemen"),
    "EG": ("EGY", "Egypt"),
    "JO": ("JOR", "Jordan"),
    "QA": ("QAT", "Qatar"),
    "AE": ("ARE", "United Arab Emirates"),
}

# CAMEO root codes kept as geopolitical tension events.
TENSION_THEMES = {
    "13": "Threaten",
    "14": "Protest",
    "15": "Exhibit force posture",
    "16": "Reduce relations",
    "17": "Coerce",
    "18": "Assault",
    "19": "Fight",
}

# Central-bank policy-rate series on FRED: (series id, bank code, bank name, country iso3, country name)
POLICY_RATES = [
    ("DFEDTARU", "FED", "Federal Reserve", "USA", "United States"),
    ("ECBDFR", "ECB", "European Central Bank", "EUR", "Euro area"),
]

UPSERT_EVENTS = """
UNWIND $rows AS r
MERGE (e:Event {event_id: r.event_id})
SET e.date = date(r.date), e.title = r.title, e.cameo_code = r.cameo_code, e.goldstein = r.goldstein,
    e.avg_tone = r.avg_tone, e.num_mentions = r.num_mentions, e.source_url = r.source_url
MERGE (c:Country {iso3: r.iso3})
ON CREATE SET c.name = r.country_name
MERGE (e)-[:OCCURRED_IN]->(c)
MERGE (t:Theme {code: r.theme_code})
ON CREATE SET t.label = r.theme_label
MERGE (e)-[:HAS_THEME]->(t)
MERGE (d:TradingDay {date: date(r.date)})
ON CREATE SET d.is_trading_day = false
MERGE (e)-[:ON_DAY]->(d)
"""

UPDATE_DAY_COUNTS = """
MATCH (d:TradingDay)
OPTIONAL MATCH (e:Event)-[:ON_DAY]->(d)
WITH d, count(e) AS n
SET d.event_count = n
"""


def _float(text: str, default: float = 0.0) -> float:
    """Parse a float, returning `default` when the field is empty or malformed."""
    try:
        return float(text)
    except ValueError:
        return default


def gdelt_event(fields: list[str]) -> dict | None:
    """Convert one GDELT row to an event dict, or None when it is out of scope or malformed."""
    if len(fields) < MIN_COLUMNS or fields[COL_ROOT_CODE] not in TENSION_THEMES:
        return None
    country = FIPS_TO_ISO3.get(fields[COL_GEO_COUNTRY])
    if country is None or len(fields[COL_DATE]) != 8:
        return None
    day = fields[COL_DATE]
    actors = " / ".join(a for a in (fields[COL_ACTOR1], fields[COL_ACTOR2]) if a) or "unknown actors"
    return {
        "event_id": f"GDELT-{fields[COL_ID]}",
        "date": f"{day[:4]}-{day[4:6]}-{day[6:]}",
        "title": f"{actors}: {TENSION_THEMES[fields[COL_ROOT_CODE]].lower()} ({fields[COL_GEO_NAME] or country[1]})",
        "cameo_code": fields[COL_EVENT_CODE],
        "goldstein": _float(fields[COL_GOLDSTEIN]),
        "avg_tone": _float(fields[COL_TONE]),
        "num_mentions": int(_float(fields[COL_MENTIONS])),
        "source_url": fields[COL_URL],
        "iso3": country[0],
        "country_name": country[1],
        "theme_code": f"CAMEO_{fields[COL_ROOT_CODE]}",
        "theme_label": TENSION_THEMES[fields[COL_ROOT_CODE]],
    }


def gdelt_events(lines: list[str], top: int, min_mentions: int, only_date: str | None = None) -> list[dict]:
    """Parse one daily file, keep the `top` most mentioned in-scope events (dated `only_date` if given)."""
    events = []
    for fields in csv.reader(lines, delimiter="\t"):
        event = gdelt_event(fields)
        if event and event["num_mentions"] >= min_mentions and only_date in (None, event["date"]):
            events.append(event)
    events.sort(key=lambda e: e["num_mentions"], reverse=True)
    return events[:top]


def fetch_gdelt_day(day: date) -> list[str]:
    """Download (cached) one daily GDELT file and return its lines. A missing file gives an empty list."""
    stamp = day.strftime("%Y%m%d")
    target = RAW_DIR / "gdelt" / f"{stamp}.export.CSV.zip"
    try:
        download(GDELT_URL.format(day=stamp), target, timeout=120)
    except OSError as exc:
        print(f"  {stamp}: not available ({exc})")
        return []
    with zipfile.ZipFile(target) as archive:
        name = archive.namelist()[0]
        return io.TextIOWrapper(archive.open(name), encoding="utf-8", errors="replace").read().splitlines()


def central_bank_events(points: list[tuple[str, float]], bank: str, name: str, iso3: str, country: str) -> list[dict]:
    """One event per change of a policy rate. The rate level before and after goes in the title."""
    events, previous = [], None
    for day, rate in points:
        if previous is not None and rate != previous:
            verb = "raises" if rate > previous else "cuts"
            events.append(
                {
                    "event_id": f"CB-{bank}-{day}",
                    "date": day,
                    "title": f"{name} {verb} its policy rate from {previous:.2f} to {rate:.2f} percent",
                    "cameo_code": "",
                    "goldstein": 0.0,
                    "avg_tone": 0.0,
                    "num_mentions": 0,
                    "source_url": "https://fred.stlouisfed.org/",
                    "iso3": iso3,
                    "country_name": country,
                    "theme_code": "MONETARY_POLICY",
                    "theme_label": "Monetary policy decision",
                }
            )
        previous = rate
    return events


def fetch_policy_rate(fred_id: str, start: str, end: str) -> list[tuple[str, float]]:
    """Download (cached) a policy-rate series. The first point is only the base level, it creates no event."""
    target = RAW_DIR / "fred" / f"{fred_id}_{start}_{end}.csv"
    download(FRED_URL.format(fred_id=fred_id, start=start, end=end), target)
    return parse_fred_csv(target.read_text(encoding="utf-8"))


def collect(args: argparse.Namespace) -> list[dict]:
    """Gather every event of the selected window."""
    events: list[dict] = []
    for fred_id, bank, name, iso3, country in POLICY_RATES:
        events += central_bank_events(fetch_policy_rate(fred_id, args.start, args.end), bank, name, iso3, country)
    if not args.skip_gdelt:
        by_day: dict[str, int] = defaultdict(int)
        for day in days_between(parse_day(args.start), parse_day(args.end), args.step):
            found = gdelt_events(fetch_gdelt_day(day), args.top, args.min_mentions, day.isoformat())
            by_day[day.isoformat()] = len(found)
            events += found
        print(f"GDELT events kept per sampled day: {dict(by_day)}")
    return events


def main() -> None:
    """Command-line entry point."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--start", default="2026-02-01")
    parser.add_argument("--end", default="2026-07-31")
    parser.add_argument("--step", type=int, default=1, help="keep one GDELT day out of N")
    parser.add_argument("--top", type=int, default=25, help="events kept per day")
    parser.add_argument("--min-mentions", type=int, default=20)
    parser.add_argument("--skip-gdelt", action="store_true")
    args = parser.parse_args()
    events = collect(args)
    with get_driver().session() as session:
        count = run_batches(session, UPSERT_EVENTS, events)
        session.run(UPDATE_DAY_COUNTS).consume()
    print(f"Loaded {count} events.")


if __name__ == "__main__":
    main()
