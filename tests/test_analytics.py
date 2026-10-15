"""Unit tests of the analytics services: no database, a fake session records queries and returns canned rows."""

import numpy as np
import pytest

from app.services.analytics import correlation, explain, gds, link_prediction, paths, queries


class FakeResult(list):
    """List of rows that also mimics the driver result (consume)."""

    def consume(self):
        """Return an empty summary."""
        return None


class FakeSession:
    """Records queries and answers with the rows given at construction."""

    def __init__(self, rows=None):
        self.rows = rows or []
        self.calls = []

    def run(self, query, **params):
        """Record a call and return the canned rows."""
        self.calls.append((query, params))
        return FakeResult(self.rows)


def test_every_query_is_named_parameterised_and_read_only():
    """Each benchmark query starts with a name comment, uses parameters and never writes."""
    for name, query in queries.BENCHMARK_QUERIES.items():
        assert query.strip().splitlines()[0] == f"// {name}"
        assert "$" in query
        assert not any(word in query for word in ("CREATE", "MERGE", "DELETE", "SET "))


def test_clamp_limit_bounds():
    """The LIMIT is always between 1 and the maximum."""
    assert queries.clamp_limit(None) == queries.DEFAULT_LIMIT
    assert queries.clamp_limit(0) == 1
    assert queries.clamp_limit(10**6) == queries.MAX_LIMIT


def test_top_countries_passes_parameters():
    """The service sends the window and a bounded limit as parameters."""
    session = FakeSession([{"iso3": "UKR", "events": 3}])
    rows = queries.top_countries(session, "2026-02-01", "2026-02-28", limit=999)
    assert rows == [{"iso3": "UKR", "events": 3}]
    assert session.calls[0][1] == {"start": "2026-02-01", "end": "2026-02-28", "limit": queries.MAX_LIMIT}


def test_events_before_moves_clamps_lag_and_moves():
    """Lag and number of moves are bounded before reaching the database."""
    session = FakeSession()
    queries.events_before_moves(session, "BRENT", "2026-02-01", "2026-03-01", max_lag=99, top_moves=0, theme="CAMEO_19")
    params = session.calls[0][1]
    assert params["max_lag"] == 7 and params["top_moves"] == 1 and params["theme"] == "CAMEO_19"


def test_pearson_known_values_and_degenerate_cases():
    """Perfect correlations give +/-1; constant or too short series give None."""
    assert correlation.pearson([1, 2, 3, 4], [2, 4, 6, 8]) == pytest.approx(1.0)
    assert correlation.pearson([1, 2, 3, 4], [8, 6, 4, 2]) == pytest.approx(-1.0)
    assert correlation.pearson([1, 1, 1, 1], [1, 2, 3, 4]) is None
    assert correlation.pearson([1, 2], [1, 2]) is None


def test_aligned_samples_uses_the_lagged_calendar_day():
    """A lag of 1 pairs the return of a day with the event count of the day before (0 when none)."""
    counts = {"2026-03-01": 5}
    xs, ys = correlation.aligned_samples(counts, [("2026-03-02", 0.1), ("2026-03-03", -0.1)], 1)
    assert xs == [5.0, 0.0] and ys == [0.1, -0.1]


def test_correlations_for_theme_finds_a_planted_lag():
    """If returns copy the event counts one day later, lag 1 has the highest correlation."""
    days = [f"2026-03-{d:02d}" for d in range(1, 29)]
    rng = np.random.default_rng(0)
    counts = {d: int(rng.integers(0, 10)) for d in days}
    returns = [(days[i], float(counts[days[i - 1]])) for i in range(1, len(days))]
    rows = correlation.correlations_for_theme(counts, returns, lags=(0, 1, 2), min_samples=10)
    best = max(rows, key=lambda r: r["corr"])
    assert best["lag_days"] == 1 and best["corr"] == pytest.approx(1.0)


def test_correlations_for_theme_needs_enough_samples():
    """Too few days give no correlation at all."""
    assert correlation.correlations_for_theme({"2026-03-01": 1}, [("2026-03-02", 0.1)], min_samples=30) == []


def test_compute_theme_correlations_sorts_by_absolute_value():
    """Rows of all themes are returned sorted by |corr| and carry the series id."""
    days = [f"2026-04-{d:02d}" for d in range(1, 31)]
    events = [{"theme": "CAMEO_19", "day": d, "n": i % 5} for i, d in enumerate(days)]
    returns = [{"day": d, "ret": float(i % 5)} for i, d in enumerate(days)]

    class Router(FakeSession):
        """Answers the events query then the returns query."""

        def run(self, query, **params):
            self.calls.append((query, params))
            return FakeResult(events if "events_per_day_by_theme" in query else returns)

    rows = correlation.compute_theme_correlations(Router(), "BRENT", "2026-04-01", "2026-04-30", lags=(0,))
    assert rows[0]["theme"] == "CAMEO_19" and rows[0]["series_id"] == "BRENT" and rows[0]["corr"] == pytest.approx(1.0)


def test_store_correlations_is_idempotent_merge_without_causal_wording():
    """The write uses MERGE on the lag, stores the window length and never says cause."""
    session = FakeSession()
    rows = [{"theme": "CAMEO_19", "series_id": "BRENT", "lag_days": 1, "corr": 0.2, "n": 120}]
    assert correlation.store_correlations(session, rows, "2026-02-01", "2026-07-31") == 1
    query, params = session.calls[0]
    assert "MERGE (t)-[c:CORRELATES_WITH {lag_days: $lag_days}]->(s)" in query
    assert params["window_days"] == 181 and "caus" not in query.lower()


def test_paths_depth_is_validated_and_injected_as_integer():
    """The depth must be 1..6 and ends up in the pattern as a plain integer."""
    session = FakeSession()
    paths.paths_between_countries(session, "ukr", "rus", max_hops=4)
    query, params = session.calls[0]
    assert "[*1..4]" in query and params["iso_a"] == "UKR"
    for bad in (0, 7):
        with pytest.raises(ValueError):
            paths.paths_event_to_series(session, "GDELT-1", "BRENT", max_hops=bad)
    with pytest.raises(ValueError):
        paths.paths_between_countries(session, "UKR", "RUS", max_hops="4; MATCH (n) DETACH DELETE n")


def test_gds_runs_project_algorithms_then_drops():
    """The projection is created first, the algorithms run on it, and it is always dropped at the end."""
    session = FakeSession([{"graphName": "g"}])
    gds.run_gds(session, limit=5)
    names = [q.strip().splitlines()[0] for q, _ in session.calls]
    assert "CALL gds.graph.drop($name, false) YIELD graphName RETURN graphName" in names[0]
    assert any("gds.graph.project" in q for q, _ in session.calls)
    assert any("gds.pageRank" in q for q, _ in session.calls) and any("gds.louvain" in q for q, _ in session.calls)
    assert "gds.graph.drop" in session.calls[-1][0]


def test_count_db_hits_and_operators_walk_the_plan():
    """Hits are summed over the tree and operators are listed from the root."""
    plan = {"operatorType": "ProduceResults", "dbHits": 1, "children": [{"operatorType": "NodeIndexSeek", "dbHits": 7}]}
    assert explain.count_db_hits(plan) == 8
    assert explain.operators(plan) == ["ProduceResults", "NodeIndexSeek"]
    assert explain.count_db_hits(None) == 0


def make_series(size=120, seed=1):
    """Events of one theme on the day before every large move: a learnable signal."""
    rng = np.random.default_rng(seed)
    moves = rng.random(size)
    big = moves > 0.75
    counts = np.zeros(size)
    counts[1:] = np.where(big[1:], 6, 0) + rng.integers(0, 2, size - 1)
    return counts, moves


def test_build_dataset_features_use_only_previous_days():
    """The features of a day are the event counts of the days before it, never of the day itself."""
    events = [{"theme": "A", "day": "2026-03-01", "n": 4}, {"theme": "A", "day": "2026-03-02", "n": 9}]
    days, features, moves, themes = link_prediction.build_dataset(events, [("2026-03-02", -0.5)], lookback=1)
    assert days == ["2026-03-02"] and themes == ["A"] and features.tolist() == [[4.0]] and moves.tolist() == [0.5]


def test_auc_perfect_and_undefined():
    """A perfect ranking gives 1; a single class gives None."""
    assert link_prediction.auc(np.array([0, 0, 1, 1]), np.array([0.1, 0.2, 0.8, 0.9])) == pytest.approx(1.0)
    assert link_prediction.auc(np.array([1, 1]), np.array([0.1, 0.2])) is None


def test_train_and_evaluate_learns_planted_signal_on_the_future():
    """A real signal gives a test AUC well above chance, and a too short history gives no model."""
    counts, moves = make_series()
    model = link_prediction.train_and_evaluate(counts.reshape(-1, 1), moves)
    assert model["auc_test"] > 0.8 and model["weights"][0] > 0
    assert model["train_days"] == int(len(moves) * 0.7)
    assert link_prediction.train_and_evaluate(counts[:20].reshape(-1, 1), moves[:20]) is None


def test_store_claims_are_hypotheses_with_neutral_rationale():
    """Claims are written as hypothesis, linked to evidence events, with wording that is not causal."""
    session = FakeSession()
    result = {"series_id": "BRENT", "claims": [{"theme": "CAMEO_19", "weight": 0.9, "confidence": 0.7}]}
    assert link_prediction.store_claims(session, result, evidence={"CAMEO_19": ["GDELT-1"]}) == 1
    claim_query, claim_params = session.calls[0]
    assert "c.status = 'hypothesis'" in claim_query and "cause" in claim_params["rationale"]
    assert "not a proven cause" in claim_params["rationale"]
    assert "ABOUT_EVENT" in session.calls[1][0]
