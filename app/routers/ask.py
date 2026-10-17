"""POST /api/ask: the agent answers a question from the graph."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.agent.graph import run_agent
from app.agent.llm import LLM, LLMUnavailable, get_llm
from app.dependencies import get_session
from app.models.agent import AgentAnswer, AskRequest

router = APIRouter(prefix="/api", tags=["agent"])


def llm_dependency() -> LLM:
    """The configured model, or HTTP 503 when it is not available."""
    try:
        return get_llm()
    except LLMUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/ask", response_model=AgentAnswer)
def ask(
    body: AskRequest, session: Annotated[object, Depends(get_session)], llm: Annotated[LLM, Depends(llm_dependency)]
):
    """Answer a question with graph paths, the Cypher used, and a status (verified or hypothesis)."""
    try:
        return run_agent(body.question, session, llm)
    except LLMUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
