"""Unit tests of the agent guardrails (no database, no model)."""

import pytest

from app.agent import guardrails as g

GOOD = "MATCH (e:Event)-[:OCCURRED_IN]->(c:Country {iso3: $iso}) WHERE e.date >= date($start) RETURN e.title, c.name"


def test_schema_is_read_from_the_graph_contract():
    """Labels, relationship types and properties come from docs/GRAPH_CONTRACT.md."""
    schema = g.load_schema()
    assert {"Event", "Country", "TradingDay", "PriceSeries", "Claim"} <= schema["labels"]
    assert {"OCCURRED_IN", "ON_DAY", "PRICE_ON", "CORRELATES_WITH", "ABOUT_EVENT"} <= schema["relationships"]
    assert {"event_id", "iso3", "ret_1d", "lag_days", "status"} <= schema["properties"]


def test_valid_query_passes_and_gets_a_limit():
    """A read query on known names is accepted and a LIMIT is added."""
    assert g.validate_cypher(GOOD).endswith(f"LIMIT {g.DEFAULT_LIMIT}")


@pytest.mark.parametrize(
    "query",
    [
        "MATCH (e:Event) DELETE e",
        "MATCH (e:Event) DETACH DELETE e",
        "CREATE (:Event {event_id: 'x'})",
        "MATCH (e:Event) SET e.title = 'x' RETURN e",
        "MERGE (c:Country {iso3: 'FRA'}) RETURN c",
        "MATCH (e:Event) REMOVE e.title RETURN e",
        "LOAD CSV FROM 'http://x' AS r RETURN r",
        "CALL db.labels()",
        "CALL gds.graph.drop('geo_events')",
        "MATCH (e:Event) RETURN e; MATCH (n) DETACH DELETE n",
        "DROP INDEX event_date",
        "EXPLAIN MATCH (e:Event) RETURN e",
    ],
)
def test_write_or_unsafe_queries_are_rejected(query):
    """Guardrail 1: writes, CALL, several statements and unknown starts are blocked."""
    with pytest.raises(g.GuardrailError):
        g.validate_cypher(query)


def test_keywords_inside_strings_and_comments_are_ignored():
    """A word such as DELETE inside a string or a comment is not a clause."""
    query = "// DELETE everything\nMATCH (e:Event) WHERE e.title CONTAINS 'DELETE and CREATE' RETURN e.title"
    assert g.validate_cypher(query).startswith("// DELETE")


@pytest.mark.parametrize(
    "query, message",
    [
        ("MATCH (p:Person) RETURN p", "Unknown label: Person"),
        ("MATCH (e:Event)-[:LOVES]->(c:Country) RETURN e", "Unknown relationship type: LOVES"),
        ("MATCH (e:Event) RETURN e.password", "Unknown property: password"),
        ("MATCH (c:Country {secret: 1}) RETURN c", "Unknown property: secret"),
    ],
)
def test_schema_check_rejects_unknown_names(query, message):
    """Guardrail 2: names that are not in the contract are rejected."""
    with pytest.raises(g.GuardrailError, match=message):
        g.validate_cypher(query)


def test_decimal_numbers_are_not_mistaken_for_properties():
    """0.5 is a number, not the property `5` of a variable."""
    assert "LIMIT" in g.validate_cypher("MATCH (e:Event) WHERE e.goldstein < -0.5 RETURN e.title")


@pytest.mark.parametrize("pattern", ["[*]", "[*1..]", "[*..9]", "[*2..7]"])
def test_unbounded_or_deep_traversal_is_rejected(pattern):
    """Guardrail 3a: variable-length paths need an upper bound of 6 or less."""
    with pytest.raises(g.GuardrailError, match="depth"):
        g.validate_cypher(f"MATCH p = (a:Country)-{pattern}-(b:Country) RETURN p")


@pytest.mark.parametrize("pattern", ["[*..3]", "[*1..6]", "[:ON_DAY*1..2]"])
def test_bounded_traversal_is_accepted(pattern):
    """A bound of 6 or less passes."""
    assert g.validate_cypher(f"MATCH p = (a:Country)-{pattern}-(b:Country) RETURN p")


def test_limit_is_added_capped_and_kept():
    """Guardrail 3b: missing LIMIT added, large LIMIT capped, small LIMIT kept."""
    assert g.enforce_limit("MATCH (e:Event) RETURN e;") == f"MATCH (e:Event) RETURN e LIMIT {g.DEFAULT_LIMIT}"
    assert g.enforce_limit("MATCH (e:Event) RETURN e LIMIT 5000").endswith(f"LIMIT {g.MAX_LIMIT}")
    assert g.enforce_limit("MATCH (e:Event) RETURN e LIMIT 7").endswith("LIMIT 7")


@pytest.mark.parametrize(
    "question",
    ["Should I buy Brent now?", "Dois-je acheter du pétrole ?", "Place an order on EURUSD", "Give me financial advice"],
)
def test_financial_advice_is_detected(question):
    """Guardrail 7: advice and order requests are recognised, in English and French."""
    assert g.is_financial_advice(question)


def test_normal_questions_are_not_refused():
    """Questions about events and moves go through."""
    assert not g.is_financial_advice("Why did the US 10-year yield move after the June meeting?")


def test_causal_wording_is_found_and_rewritten():
    """Guardrail 6: causal expressions are detected and replaced by neutral ones."""
    text = "The strike caused the rise and led to a spike because of fear."
    assert set(g.find_causal_wording(text)) == {"caused", "led to", "because of"}
    rewritten = g.rewrite_causal(text)
    assert not g.find_causal_wording(rewritten) and "was followed by" in rewritten


def test_neutral_wording_is_untouched():
    """A statement without cause is not modified."""
    text = "Brent rose the day after the event."
    assert g.rewrite_causal(text) == text and g.find_causal_wording(text) == []
