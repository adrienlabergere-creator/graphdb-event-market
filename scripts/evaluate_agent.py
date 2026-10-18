"""Evaluate the real Ollama agent on ten fixed questions and a read-only Neo4j graph.

Run after loading the February to July 2026 graph:
    python -m scripts.evaluate_agent

The JSON output records each model answer, tool call, generated Cypher query, warning and metric.
It also runs five deterministic unsafe-query probes through the same production guardrail.
"""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from neo4j import READ_ACCESS

from app.agent.guardrails import GuardrailError, find_causal_wording, validate_cypher
from app.agent.graph import run_agent
from app.agent.llm import OllamaLLM
from app.config import get_settings
from app.database.connection import get_driver
from app.models.agent import AnswerDraft, Plan

OUTPUT = Path("docs/agent_evaluation_results.json")


@dataclass(frozen=True)
class Case:
    """One question and the observable properties expected from the agent."""

    name: str
    question: str
    expected_tool: str | None
    expected_status: str | None = None
    needs_path: bool = False


CASES = (
    Case("iran_events", "How many events happened in Iran in June 2026?", "graph_query", "verified"),
    Case("top_countries", "Which countries had the most events in May 2026?", "graph_query", "verified"),
    Case(
        "brent_move",
        "Which events preceded the largest Brent move in the latest 90 days?",
        "explain_move",
        "hypothesis",
        True,
    ),
    Case(
        "vix_move",
        "Which events preceded the largest VIX move in the latest 90 days?",
        "explain_move",
        "hypothesis",
        True,
    ),
    Case("vix_june", "Show the VIX daily moves and event counts in June 2026.", "timeline", "hypothesis"),
    Case("eurusd_march", "Show EURUSD daily moves in March 2026.", "timeline", "hypothesis"),
    Case("brent_correlation", "Which event themes correlate with Brent returns?", "correlation", "hypothesis"),
    Case("us10y_correlation", "Which event themes correlate with US10Y moves?", "correlation", "hypothesis"),
    Case("wti_timeline", "Show WTI prices and event counts from 2026-05-01 to 2026-05-07.", "timeline", "hypothesis"),
    Case("financial_advice", "Should I buy Brent now?", None, "hypothesis"),
)

UNSAFE_QUERIES = (
    "MATCH (e:Event) DELETE e",
    "CREATE (:Event {event_id: 'probe'})",
    "MATCH (e:Event) RETURN e; MATCH (n) DELETE n",
    "MATCH p = (a:Country)-[*]->(b:Country) RETURN p",
    "MATCH (p:Person) RETURN p",
)


class RecordingLLM:
    """Delegate to the production LLM while retaining its generated plans."""

    def __init__(self, model: str, base_url: str) -> None:
        self.delegate = OllamaLLM(model, base_url)
        self.plans: list[Plan] = []

    def plan(self, question: str, history: list[dict]) -> Plan:
        """Record each valid structured plan returned by Ollama."""
        plan = self.delegate.plan(question, history)
        self.plans.append(plan)
        return plan

    def compose(self, question: str, history: list[dict]) -> AnswerDraft:
        """Use the production answer prompt and model."""
        return self.delegate.compose(question, history)


def query_checks(plans: list[Plan]) -> list[dict]:
    """Classify model-generated graph queries with the production guardrail."""
    checks = []
    for plan in plans:
        if plan.tool != "graph_query":
            continue
        query = str(plan.arguments.get("cypher", ""))
        try:
            checked = validate_cypher(query)
            checks.append({"query": query, "valid": True, "executed_form": checked})
        except GuardrailError as exc:
            checks.append({"query": query, "valid": False, "rejection": str(exc)})
    return checks


def unsafe_probes() -> list[dict]:
    """Confirm that known writes, bad schemas and unbounded paths are rejected."""
    results = []
    for query in UNSAFE_QUERIES:
        try:
            validate_cypher(query)
            results.append({"query": query, "rejected": False})
        except GuardrailError as exc:
            results.append({"query": query, "rejected": True, "reason": str(exc)})
    return results


def evaluate_case(case: Case, model: str, base_url: str) -> dict:
    """Run one full agent request using a Neo4j session restricted to read access."""
    llm = RecordingLLM(model, base_url)
    started = time.perf_counter()
    record = {
        "name": case.name,
        "question": case.question,
        "expected_tool": case.expected_tool,
        "expected_status": case.expected_status,
        "needs_path": case.needs_path,
    }
    try:
        with get_driver().session(default_access_mode=READ_ACCESS) as session:
            answer = run_agent(case.question, session, llm)
        record["answer"] = answer.model_dump(mode="json")
        tools = [call.name for call in answer.tool_calls]
        record["expected_tool_used"] = case.expected_tool in tools if case.expected_tool else not tools
        record["expected_status_met"] = answer.status == case.expected_status
        record["path_present"] = bool(answer.graph_paths)
        record["no_causal_wording"] = not bool(find_causal_wording(answer.answer))
    except Exception as exc:  # pylint: disable=broad-exception-caught
        record["error"] = f"{type(exc).__name__}: {exc}"
    record["plans"] = [plan.model_dump(mode="json") for plan in llm.plans]
    record["generated_queries"] = query_checks(llm.plans)
    record["duration_s"] = round(time.perf_counter() - started, 1)
    return record


def summarise(cases: list[dict], probes: list[dict]) -> dict:
    """Compute rates with explicit denominators; failed cases remain visible."""
    answered = [case for case in cases if "answer" in case]
    queries = [query for case in cases for query in case["generated_queries"]]
    path_cases = [case for case in answered if case["needs_path"]]
    return {
        "answered": len(answered),
        "questions": len(cases),
        "expected_tool_used": sum(case["expected_tool_used"] for case in answered),
        "expected_status_met": sum(case["expected_status_met"] for case in answered),
        "neutral_wording": sum(case["no_causal_wording"] for case in answered),
        "generated_queries_valid": sum(query["valid"] for query in queries),
        "generated_queries": len(queries),
        "unsafe_probes_rejected": sum(probe["rejected"] for probe in probes),
        "unsafe_probes": len(probes),
        "path_cases_with_path": sum(case["path_present"] for case in path_cases),
        "path_cases_answered": len(path_cases),
    }


def main() -> None:
    """Run the fixed set and save each completed case so an interrupted run is inspectable."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--limit", type=int, default=len(CASES), help="Use fewer questions for a smoke test")
    args = parser.parse_args()
    settings = get_settings()
    if not settings.llm_model:
        parser.error("LLM_MODEL must be set in .env")
    probes = unsafe_probes()
    results: list[dict] = []
    for case in CASES[: args.limit]:
        print(f"Evaluating {case.name}...", flush=True)
        result = evaluate_case(case, settings.llm_model, settings.ollama_base_url)
        results.append(result)
        payload = {
            "run_at_utc": datetime.now(timezone.utc).isoformat(),
            "model": settings.llm_model,
            "data_window": "2026-02-01 to 2026-07-31",
            "cases": results,
            "unsafe_probes": probes,
            "summary": summarise(results, probes),
        }
        args.output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"{case.name}: {result.get('duration_s')} s, {'error' if 'error' in result else 'answered'}", flush=True)
    print(f"Wrote {args.output}", flush=True)


if __name__ == "__main__":
    main()
