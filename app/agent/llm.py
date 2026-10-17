"""The language model behind the agent: a small interface and its Ollama implementation."""

from __future__ import annotations

import json
from typing import Any, Protocol

import httpx
from ollama import ResponseError

from app.agent.guardrails import load_schema
from app.agent.tools import TOOL_DESCRIPTIONS
from app.config import get_settings
from app.models.agent import AnswerDraft, Plan
from app.services.analytics.constants import SERIES_IDS


class LLMUnavailable(RuntimeError):
    """The model runtime cannot be reached or is not configured."""


class LLM(Protocol):
    """What the agent needs from a model. Tests replace it with a fake."""

    def plan(self, question: str, history: list[dict]) -> Plan:
        """Choose the next tool to call, or `finish`."""

    def compose(self, question: str, history: list[dict]) -> AnswerDraft:
        """Write the answer from the tool results."""


def _schema_text() -> str:
    """One-line summary of the graph schema for the prompts."""
    schema = load_schema()
    return (
        f"Labels: {', '.join(sorted(schema['labels']))}. Relationships: {', '.join(sorted(schema['relationships']))}. "
        f"Properties: {', '.join(sorted(schema['properties']))}."
    )


def _history_text(history: list[dict]) -> str:
    """Tool calls and results so far, as JSON text."""
    return json.dumps(history, default=str)[:6000]


PLAN_PROMPT = """You plan the next step of a data agent that answers questions about geopolitical events and markets.
Series ids: {series}. Tools:
{tools}
Graph schema: {schema}
The graph only covers 2026-02-01 to 2026-07-31.
`explain_move` always looks at the most recent `window` days of a series, so when the question is about a given month
or date range, use `timeline` with `start` and `end` instead.
Choose ONE tool and its arguments, or "finish" when the results so far are enough to answer.
Never repeat a call you have already made: if its result is in the history, answer "finish".
Question: {question}
Tool calls and results so far: {history}"""

COMPOSE_PROMPT = """Answer using ONLY the tool results below, in the language of the question, in at most 4 sentences.
Say that events and moves are "associated" or "followed" each other. Never say that an event caused a move.
Give a confidence between 0 and 1.
Question: {question}
Tool results: {history}"""


class OllamaLLM:
    """Local model served by Ollama, with structured output."""

    def __init__(self, model: str, base_url: str) -> None:
        # Imported here so the API starts (and tests run) even when the model runtime is not installed.
        from langchain_ollama import ChatOllama  # pylint: disable=import-outside-toplevel

        self._chat: Any = ChatOllama(model=model, base_url=base_url, temperature=0)

    def _ask(self, schema: type, prompt: str):
        """Call the model with structured output. Connection problems become LLMUnavailable."""
        try:
            return self._chat.with_structured_output(schema).invoke(prompt)
        except (ConnectionError, OSError, httpx.HTTPError, ResponseError) as exc:
            raise LLMUnavailable(f"Cannot reach the model runtime: {exc}") from exc

    def plan(self, question: str, history: list[dict]) -> Plan:
        """Choose the next tool to call, or `finish`."""
        tools = "\n".join(f"- {name}: {text}" for name, text in TOOL_DESCRIPTIONS.items())
        prompt = PLAN_PROMPT.format(
            series=", ".join(SERIES_IDS),
            tools=tools,
            schema=_schema_text(),
            question=question,
            history=_history_text(history),
        )
        return Plan.model_validate(self._ask(Plan, prompt))

    def compose(self, question: str, history: list[dict]) -> AnswerDraft:
        """Write the answer from the tool results."""
        prompt = COMPOSE_PROMPT.format(question=question, history=_history_text(history))
        return AnswerDraft.model_validate(self._ask(AnswerDraft, prompt))


def get_llm() -> LLM:
    """FastAPI dependency: the configured model, or LLMUnavailable when LLM_MODEL is empty."""
    settings = get_settings()
    if not settings.llm_model:
        raise LLMUnavailable("LLM_MODEL is not set in .env")
    return OllamaLLM(settings.llm_model, settings.ollama_base_url)
