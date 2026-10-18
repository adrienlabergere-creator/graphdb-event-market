"""The LangGraph flow: parse_question -> plan -> run_tools (loop, 5 steps maximum) -> validate -> answer."""

from __future__ import annotations

import json
import time
from typing import Any, TypedDict

from langgraph.graph import END, StateGraph
from neo4j.exceptions import ClientError
from pydantic import ValidationError

from app.agent import guardrails
from app.agent.llm import LLM
from app.agent.tools import TOOL_ERRORS, TOOLS
from app.models.agent import AgentAnswer, AnswerDraft, Plan, ToolCall

REFUSAL = "I cannot give financial advice or place orders. I can describe events and market moves that the graph links."
NO_DATA = "I could not collect usable data from the graph for this question."
REJECTED = "The model did not return a valid answer, so no answer is given."


class State(TypedDict, total=False):
    """What the graph carries from step to step."""

    question: str
    refused: bool
    plan: Plan
    steps: int
    tool_calls: list[ToolCall]
    history: list[dict]
    paths: list[list[str]]
    cypher: list[str]
    warnings: list[str]
    hypothesis: bool
    draft: AnswerDraft | None
    answer: AgentAnswer


def _signature(item: dict) -> tuple[str, str]:
    """Tool name and arguments of a history entry, in a comparable form."""
    return item["tool"], json.dumps(item["arguments"], sort_keys=True, default=str)


def repeats_earlier_call(history: list[dict]) -> bool:
    """True when the last call repeats an earlier one: it brings no new information, so the loop stops."""
    if len(history) < 2:
        return False
    return any(_signature(item) == _signature(history[-1]) for item in history[:-1])


def unique_paths(paths: list[list[str]]) -> list[list[str]]:
    """Keep the first occurrence of each graph path, in order."""
    seen: set[tuple[str, ...]] = set()
    unique: list[list[str]] = []
    for path in paths:
        key = tuple(path)
        if key not in seen:
            seen.add(key)
            unique.append(path)
    return unique


def with_retry(call, *args):
    """Guardrail 4: a malformed model output is retried once, then the error is raised."""
    try:
        return call(*args)
    except (ValidationError, ValueError):
        return call(*args)


def build_graph(session: Any, llm: LLM):
    """Compile the agent graph for one request (the session and the model are closed over)."""

    def parse_question(state: State) -> State:
        question = state["question"].strip()
        if guardrails.is_financial_advice(question):
            return {"question": question, "refused": True, "warnings": ["Refused: financial advice or order request"]}
        return {"question": question, "refused": False}

    def plan(state: State) -> State:
        try:
            chosen = with_retry(llm.plan, state["question"], state["history"])
        except (ValidationError, ValueError):
            return {"plan": Plan(tool="finish"), "warnings": state["warnings"] + ["Invalid plan from the model"]}
        if chosen.tool != "finish" and any(
            _signature(item) == _signature({"tool": chosen.tool, "arguments": chosen.arguments})
            for item in state["history"]
        ):
            return {"plan": Plan(tool="finish"), "warnings": state["warnings"] + ["Repeated tool call skipped"]}
        return {"plan": chosen}

    def run_tools(state: State) -> State:
        chosen = state["plan"]
        started = time.perf_counter()
        update: State = {"steps": state["steps"] + 1}
        try:
            result = TOOLS[chosen.tool](session, chosen.arguments)
            outcome = {"result": result.data}
            update["paths"] = state["paths"] + result.paths
            update["cypher"] = state["cypher"] + result.cypher
            update["hypothesis"] = state["hypothesis"] or result.hypothesis
        except (*TOOL_ERRORS, ClientError) as exc:
            outcome = {"error": str(exc)[:300]}
            update["warnings"] = state["warnings"] + [f"{chosen.tool} failed: {str(exc)[:120]}"]
        elapsed = int((time.perf_counter() - started) * 1000)
        update["tool_calls"] = state["tool_calls"] + [
            ToolCall(name=chosen.tool, arguments=chosen.arguments, duration_ms=elapsed)
        ]
        update["history"] = state["history"] + [{"tool": chosen.tool, "arguments": chosen.arguments, **outcome}]
        return update

    def validate(state: State) -> State:
        if not any("result" in item for item in state["history"]):
            return {"draft": None, "warnings": state["warnings"] + [NO_DATA]}
        warnings = list(state["warnings"])
        try:
            draft = with_retry(llm.compose, state["question"], state["history"])
        except (ValidationError, ValueError):
            return {"draft": None, "warnings": warnings + [REJECTED]}
        # Applied to every answer, verified ones included: the graph shows association, never a cause.
        if guardrails.find_causal_wording(draft.answer):
            draft = AnswerDraft(answer=guardrails.rewrite_causal(draft.answer), confidence=draft.confidence)
            warnings.append("Causal wording rewritten: the graph shows association, not cause")
        return {"draft": draft, "warnings": warnings}

    def answer(state: State) -> State:
        draft = state.get("draft")
        if state["refused"]:
            text, confidence = REFUSAL, 1.0
        elif draft is None:
            text, confidence = state["warnings"][-1], 0.0
        else:
            text, confidence = draft.answer, draft.confidence
        final = AgentAnswer(
            answer=text,
            status="hypothesis" if state["hypothesis"] or draft is None else "verified",
            confidence=confidence,
            tool_calls=state["tool_calls"],
            graph_paths=unique_paths(state["paths"]),
            cypher_used=state["cypher"],
            warnings=state["warnings"],
        )
        return {"answer": final}

    def after_parse(state: State) -> str:
        return "answer" if state["refused"] else "plan"

    def after_plan(state: State) -> str:
        return "validate" if state["plan"].tool == "finish" else "run_tools"

    def after_tools(state: State) -> str:
        if state["steps"] >= guardrails.MAX_STEPS or repeats_earlier_call(state["history"]):
            return "validate"
        return "plan"

    graph = StateGraph(State)
    for name, node in (
        ("parse_question", parse_question),
        ("plan", plan),
        ("run_tools", run_tools),
        ("validate", validate),
        ("answer", answer),
    ):
        graph.add_node(name, node)
    graph.set_entry_point("parse_question")
    graph.add_conditional_edges("parse_question", after_parse, {"answer": "answer", "plan": "plan"})
    graph.add_conditional_edges("plan", after_plan, {"validate": "validate", "run_tools": "run_tools"})
    graph.add_conditional_edges("run_tools", after_tools, {"validate": "validate", "plan": "plan"})
    graph.add_edge("validate", "answer")
    graph.add_edge("answer", END)
    return graph.compile()


def run_agent(question: str, session: Any, llm: LLM) -> AgentAnswer:
    """Answer a question. The result always carries its tool calls, paths, Cypher and warnings."""
    initial: State = {
        "question": question,
        "steps": 0,
        "tool_calls": [],
        "history": [],
        "paths": [],
        "cypher": [],
        "warnings": [],
        "hypothesis": False,
    }
    return build_graph(session, llm).invoke(initial)["answer"]
