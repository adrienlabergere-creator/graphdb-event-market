"""Analytics tests on a tiny graph written to Neo4j (skipped when Neo4j is not reachable).

The seed uses dates in 1999 and ids starting with `T-`, so it cannot collide with the real data. It is deleted after
each test.
"""

import pytest

from app.database.connection import get_driver
from app.services.analytics import correlation, paths, queries

pytestmark = pytest.mark.neo4j

SEED = """
UNWIND range(0, 39) AS i
MERGE (d:TradingDay {date: date('1999-01-01') + duration({days: i})})
SET d.is_trading_day = true, d.event_count = CASE WHEN i % 5 = 0 THEN 3 ELSE 0 END
MERGE (s:PriceSeries {series_id: 'T-SER'}) SET s.ticker = 'T', s.name = 'Test', s.kind = 'commodity'
MERGE (s)-[p:PRICE_ON]->(d) SET p.close = 100.0 + i, p.ret_1d = CASE WHEN i % 5 = 1 THEN 0.05 ELSE 0.001 END
WITH i, d
WHERE i % 5 = 0
MERGE (c:Country {iso3: 'TST'}) SET c.name = 'Testland'
MERGE (t:Theme {code: 'T-THEME'}) SET t.label = 'Test theme'
MERGE (e:Event {event_id: 'T-' + toString(i)})
SET e.date = d.date, e.title = 'event ' + toString(i), e.goldstein = -5.0, e.num_mentions = 100 + i
MERGE (e)-[:OCCURRED_IN]->(c)
MERGE (e)-[:HAS_THEME]->(t)
MERGE (e)-[:ON_DAY]->(d)
"""

CLEAN = """
MATCH (n) WHERE n.event_id STARTS WITH 'T-' OR n.series_id = 'T-SER' OR n.iso3 = 'TST' OR n.code = 'T-THEME'
   OR (n:TradingDay AND n.date >= date('1999-01-01') AND n.date < date('1999-03-01'))
DETACH DELETE n
"""


@pytest.fixture(name="session")
def session_fixture(neo4j_required):
    """A session on a database holding only the tiny seed graph (cleaned before and after)."""
    _ = neo4j_required
    with get_driver().session() as session:
        session.run(CLEAN).consume()
        session.run(SEED).consume()
        yield session
        session.run(CLEAN).consume()


def test_timeline_returns_one_row_per_day(session):
    """The seed has 40 days with their event count and return."""
    rows = queries.timeline(session, "T-SER", "1999-01-01", "1999-02-09")
    assert len(rows) == 40 and rows[0]["events"] == 3


def test_events_before_moves_finds_the_event_of_the_day_before(session):
    """Large moves happen the day after each event, so lag 1 is found."""
    rows = queries.events_before_moves(session, "T-SER", "1999-01-01", "1999-02-09", max_lag=1, top_moves=3)
    assert rows and all(r["lag_days"] == 1 and r["theme"] == "T-THEME" for r in rows)


def test_theme_impact_and_correlation_see_the_planted_pattern(session):
    """The theme precedes the large moves by one day: positive correlation at lag 1."""
    impact = queries.theme_impact(session, "T-SER", "1999-01-01", "1999-02-09")
    assert impact[0]["theme"] == "T-THEME"
    rows = correlation.compute_theme_correlations(session, "T-SER", "1999-01-01", "1999-02-09", lags=(1,))
    assert rows and rows[0]["corr"] > 0.9


def test_shortest_path_event_to_series_goes_through_the_day(session):
    """Event, day, series: two hops."""
    rows = paths.paths_event_to_series(session, "T-0", "T-SER")
    assert rows and rows[0]["hops"] == 2
