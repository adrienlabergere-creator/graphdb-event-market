"""Tests of the agent flow with a scripted model and a fake session (the real model is never called)."""

from fakes import MOVE_ROWS, FakeLLM, FakeSession

from app.agent.graph import REFUSAL, run_agent, unique_paths
from app.models.agent import AnswerDraft, Plan

EXPLAIN = Plan(tool="explain_move", arguments={"series_id": "BRENT", "window": 90})


def test_explain_move_answer_has_paths_tool_calls_and_is_a_hypothesis():
    """A correlation-based answer exposes its paths and tool calls and is marked hypothesis."""
    answer = run_agent("Why did Brent move?", FakeSession(MOVE_ROWS), FakeLLM([EXPLAIN]))
    assert answer.status == "hypothesis" and answer.disclaimer
    assert [c.name for c in answer.tool_calls] == ["explain_move"]
    assert answer.graph_paths == [["GDELT-1", "2026-07-29", "BRENT"]]  # identical paths are reported once
    assert answer.confidence == 0.6


def test_causal_wording_is_rewritten_for_a_hypothesis():
    """Guardrail 6 in the flow: 'caused' becomes a neutral expression and a warning is added."""
    llm = FakeLLM([EXPLAIN], answer=AnswerDraft(answer="The strike caused the rise in Brent.", confidence=0.9))
    answer = run_agent("Why did Brent move?", FakeSession(MOVE_ROWS), llm)
    assert "caused" not in answer.answer and "was followed by" in answer.answer
    assert any("Causal wording" in w for w in answer.warnings)


def test_graph_query_is_validated_limited_and_verified():
    """A facts query goes through the guardrails, gets a LIMIT, and the answer is `verified`."""
    session = FakeSession({"top": [{"iso3": "UKR", "n": 12}]})
    plan = Plan(
        tool="graph_query",
        arguments={"cypher": "// top\nMATCH (e:Event)-[:OCCURRED_IN]->(c:Country) RETURN c.iso3, count(e) AS n"},
    )
    llm = FakeLLM([plan], answer=AnswerDraft(answer="Ukraine has 12 events.", confidence=0.9))
    answer = run_agent("Which country has the most events?", session, llm)
    assert answer.status == "verified"
    assert answer.cypher_used[0].endswith("LIMIT 100") and session.queries[0].endswith("LIMIT 100")


def test_unsafe_cypher_is_rejected_and_nothing_is_executed():
    """Guardrail 1 in the flow: a DELETE never reaches the database and the answer says no data."""
    session = FakeSession()
    plan = Plan(tool="graph_query", arguments={"cypher": "MATCH (e:Event) DETACH DELETE e"})
    answer = run_agent("Delete the events", session, FakeLLM([plan]))
    assert session.queries == [] and answer.confidence == 0.0 and answer.tool_calls[0].name == "graph_query"
    assert any("Forbidden keyword" in w for w in answer.warnings)


def test_financial_advice_is_refused_without_any_tool_call():
    """Guardrail 7 in the flow."""
    answer = run_agent("Should I buy Brent now?", FakeSession(), FakeLLM([EXPLAIN]))
    assert answer.answer == REFUSAL and answer.tool_calls == [] and answer.warnings


def test_the_loop_stops_after_five_steps():
    """The agent never runs more than 5 tool calls, even when every plan asks for something new."""
    plans = [
        Plan(tool="timeline", arguments={"series_id": "BRENT", "start": f"2026-07-{day:02d}", "end": "2026-07-31"})
        for day in range(1, 11)
    ]
    answer = run_agent("Show Brent", FakeSession(MOVE_ROWS), FakeLLM(plans))
    assert len(answer.tool_calls) == 5


def test_malformed_answer_is_retried_once_then_rejected():
    """Guardrail 4: one malformed output is retried, two in a row are rejected."""
    retried = FakeLLM([EXPLAIN], bad_compose=1)
    assert run_agent("Why did Brent move?", FakeSession(MOVE_ROWS), retried).confidence == 0.6
    assert retried.compose_calls == 2
    rejected = run_agent("Why did Brent move?", FakeSession(MOVE_ROWS), FakeLLM([EXPLAIN], bad_compose=2))
    assert rejected.confidence == 0.0 and any("valid answer" in w for w in rejected.warnings)


def test_bad_tool_arguments_are_a_warning_not_a_crash():
    """An unknown series is reported as a warning and the agent still answers."""
    plan = Plan(tool="explain_move", arguments={"series_id": "GOLD"})
    answer = run_agent("Why did gold move?", FakeSession(MOVE_ROWS), FakeLLM([plan]))
    assert answer.confidence == 0.0 and any("Unknown series" in w for w in answer.warnings)


def test_unreachable_model_runtime_is_reported_as_unavailable():
    """A closed Ollama port gives LLMUnavailable (HTTP 503 in the API), not a raw network error."""
    import pytest  # pylint: disable=import-outside-toplevel

    from app.agent.llm import LLMUnavailable, OllamaLLM  # pylint: disable=import-outside-toplevel

    with pytest.raises(LLMUnavailable):
        OllamaLLM("any-model", "http://127.0.0.1:9").plan("Why did Brent move?", [])


def test_a_repeated_tool_call_stops_the_loop():
    """A repeated plan is skipped before another database call and the agent stops."""
    answer = run_agent("Why did Brent move?", FakeSession(MOVE_ROWS), FakeLLM([EXPLAIN, EXPLAIN, EXPLAIN]))
    assert [c.name for c in answer.tool_calls] == ["explain_move"]
    assert "Repeated tool call skipped" in answer.warnings


def test_graph_paths_are_reported_without_duplicates():
    """The same path collected twice appears once in the answer."""
    repeated = [["GDELT-1", "2026-07-29", "BRENT"], ["GDELT-2", "2026-07-29", "BRENT"]] * 3
    assert unique_paths(repeated) == [["GDELT-1", "2026-07-29", "BRENT"], ["GDELT-2", "2026-07-29", "BRENT"]]


def test_causal_wording_is_rewritten_on_a_verified_answer_too():
    """The graph never proves a cause, so the filter applies even when the answer is verified."""
    plan = Plan(tool="graph_query", arguments={"cypher": "MATCH (e:Event) RETURN e.event_id"})
    llm = FakeLLM([plan], answer=AnswerDraft(answer="Iran events caused the Brent spike.", confidence=0.9))
    answer = run_agent("Why did Brent spike?", FakeSession(), llm)
    assert answer.status == "verified"
    assert "caused" not in answer.answer and "was followed by" in answer.answer
    assert any("Causal wording" in w for w in answer.warnings)
