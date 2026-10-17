"""Pydantic models of the agent (see docs/AGENT_SPEC.md)."""

from typing import Any, Literal

from pydantic import BaseModel, Field

from app.models.api import DISCLAIMER

ToolName = Literal["graph_query", "correlation", "timeline", "explain_move"]


class AskRequest(BaseModel):
    """Body of POST /api/ask."""

    question: str = Field(min_length=3, max_length=500)


class Plan(BaseModel):
    """Next step chosen by the LLM: call one tool, or finish."""

    tool: ToolName | Literal["finish"]
    arguments: dict[str, Any] = Field(default_factory=dict)


class AnswerDraft(BaseModel):
    """Answer written by the LLM from the tool results."""

    answer: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)


class ToolCall(BaseModel):
    """One tool call, kept to show how the answer was built."""

    name: str
    arguments: dict[str, Any]
    duration_ms: int


class AgentAnswer(BaseModel):
    """Structured answer returned by POST /api/ask."""

    answer: str
    status: Literal["verified", "hypothesis"]
    confidence: float = Field(ge=0.0, le=1.0)
    tool_calls: list[ToolCall]
    graph_paths: list[list[str]]
    cypher_used: list[str]
    warnings: list[str]
    disclaimer: str = DISCLAIMER
