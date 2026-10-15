"""Tests for the ingestion scripts (no network, no database: parsing, selection and query shape)."""

from datetime import date

from scripts import ingest_common, ingest_events, ingest_prices

FRED_TEXT = "DATE,VALUE\n2022-03-01,100.0\n2022-03-02,.\n2022-03-03,110.0\n2022-03-04,99.0\n"


class FakeSession:
    """Records the queries it is asked to run."""

    def __init__(self):
        self.calls = []

    def run(self, query, **params):
        """Record a call and return an object with consume()."""
        self.calls.append((query, params))
        return self

    def consume(self):
        """Mimic the driver result summary."""
        return None


def gdelt_row(over=None):
    """Build a 58-column GDELT row with sensible defaults."""
    fields = [""] * 58
    values = {
        0: "1",
        1: "20220301",
        6: "RUSSIA",
        16: "UKRAINE",
        26: "190",
        28: "19",
        30: "-10",
        31: "120",
        34: "-5.5",
        50: "Kyiv",
        51: "UP",
        57: "http://example.org/a",
    }
    values.update(over or {})
    for index, value in values.items():
        fields[index] = value
    return "\t".join(fields)


def test_chunked_splits_in_batches():
    """Batches never exceed the size and keep every item."""
    batches = list(ingest_common.chunked([{"i": i} for i in range(5)], size=2))
    assert [len(b) for b in batches] == [2, 2, 1]


def test_run_batches_uses_unwind_param_and_counts():
    """Each batch is sent as $rows with the extra parameters."""
    session = FakeSession()
    total = ingest_common.run_batches(session, "UNWIND $rows AS r RETURN r", [{"a": 1}] * 3, size=2, series_id="X")
    assert total == 3 and len(session.calls) == 2
    assert session.calls[0][1]["series_id"] == "X" and len(session.calls[0][1]["rows"]) == 2


def test_days_between_with_step():
    """Every step-th day is returned, both ends included when aligned."""
    days = ingest_common.days_between(date(2022, 3, 1), date(2022, 3, 15), 7)
    assert days == [date(2022, 3, 1), date(2022, 3, 8), date(2022, 3, 15)]


def test_parse_fred_csv_skips_missing_values():
    """The '.' marker used by FRED is dropped."""
    assert ingest_prices.parse_fred_csv(FRED_TEXT) == [
        ("2022-03-01", 100.0),
        ("2022-03-03", 110.0),
        ("2022-03-04", 99.0),
    ]


def test_compute_returns_price_and_rate():
    """Simple return for prices, difference in points for rates, nothing for the first day."""
    points = ingest_prices.parse_fred_csv(FRED_TEXT)
    price = ingest_prices.compute_returns(points, "fx")
    rate = ingest_prices.compute_returns(points, "rate")
    assert price[0]["ret_1d"] is None
    assert abs(price[1]["ret_1d"] - 0.10) < 1e-9
    assert abs(rate[1]["ret_1d"] - 10.0) < 1e-9


def test_series_specs_are_consistent():
    """Identifiers are unique and every tracked target is a Commodity or a Currency."""
    ids = [s.series_id for s in ingest_prices.SERIES]
    assert len(ids) == len(set(ids))
    assert all(s.target is None or s.target[0] in ("Commodity", "Currency") for s in ingest_prices.SERIES)


def test_load_series_runs_merge_queries():
    """Loading a series creates the series, links its target and sends the prices in UNWIND batches."""
    session = FakeSession()
    spec = ingest_prices.SERIES[0]
    count = ingest_prices.load_series(session, spec, ingest_prices.parse_fred_csv(FRED_TEXT))
    queries = [q for q, _ in session.calls]
    assert count == 3
    assert "MERGE (s:PriceSeries" in queries[0] and "MERGE (x:Commodity" in queries[1] and "UNWIND $rows" in queries[2]


def test_queries_are_idempotent_and_batched():
    """Every write uses MERGE and the bulk ones use UNWIND, so reruns create no duplicates."""
    for query in (ingest_prices.UPSERT_SERIES, ingest_prices.UPSERT_PRICES, ingest_events.UPSERT_EVENTS):
        assert "MERGE" in query and "CREATE (" not in query
    assert "UNWIND $rows" in ingest_prices.UPSERT_PRICES and "UNWIND $rows" in ingest_events.UPSERT_EVENTS


def test_gdelt_event_conversion():
    """A tension event in a known country is converted with ISO3 country, theme and ISO date."""
    event = ingest_events.gdelt_event(gdelt_row().split("\t"))
    assert event["event_id"] == "GDELT-1" and event["date"] == "2022-03-01"
    assert event["iso3"] == "UKR" and event["theme_code"] == "CAMEO_19" and event["num_mentions"] == 120


def test_gdelt_event_filters_out_of_scope_rows():
    """Cooperative events, unknown countries and short rows are ignored."""
    assert ingest_events.gdelt_event(gdelt_row({28: "04"}).split("\t")) is None
    assert ingest_events.gdelt_event(gdelt_row({51: "ZZ"}).split("\t")) is None
    assert ingest_events.gdelt_event(["too", "short"]) is None


def test_gdelt_events_keeps_top_n_by_mentions():
    """Only the most mentioned events above the threshold are kept, in decreasing order."""
    lines = [gdelt_row({0: str(i), 31: str(m)}) for i, m in enumerate([5, 300, 50, 200])]
    kept = ingest_events.gdelt_events(lines, top=2, min_mentions=20)
    assert [e["num_mentions"] for e in kept] == [300, 200]


def test_central_bank_events_from_rate_changes():
    """A change of the policy rate is an event; an unchanged day is not."""
    points = [("2022-03-01", 0.25), ("2022-03-02", 0.25), ("2022-03-17", 0.50), ("2022-05-05", 1.00)]
    events = ingest_events.central_bank_events(points, "FED", "Federal Reserve", "USA", "United States")
    assert [e["event_id"] for e in events] == ["CB-FED-2022-03-17", "CB-FED-2022-05-05"]
    assert "raises" in events[0]["title"] and events[0]["theme_code"] == "MONETARY_POLICY"


def test_day_counts_query_aggregates_with_with():
    """The post-load step aggregates events per day with WITH and writes the result back, so it can be rerun safely."""
    query = ingest_events.UPDATE_DAY_COUNTS
    assert "WITH d, count(e) AS n" in query and "SET d.event_count = n" in query


def test_gdelt_events_keeps_only_events_dated_the_file_day():
    """A daily file also holds older events; only those dated that day are kept."""
    lines = [gdelt_row({0: "1"}), gdelt_row({0: "2", 1: "20220228"})]
    kept = ingest_events.gdelt_events(lines, top=5, min_mentions=20, only_date="2022-03-01")
    assert [e["event_id"] for e in kept] == ["GDELT-1"]
