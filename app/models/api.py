"""Pydantic models of the analytical endpoints (see docs/API_CONTRACT.md)."""

from typing import Literal

from pydantic import BaseModel

DISCLAIMER = (
    "Statistical association measured on a short sample. It is a hypothesis, not a proven cause, "
    "and not financial advice."
)


class CorrelationItem(BaseModel):
    """Correlation between a theme and a series, for one lag."""

    theme: str
    series: str
    corr: float
    n: int
    lag_days: int
    status: Literal["hypothesis"] = "hypothesis"
    disclaimer: str = DISCLAIMER


class Candidate(BaseModel):
    """An event that happened shortly before a price move."""

    event_id: str
    title: str
    score: float
    path: list[str]


class ExplainMove(BaseModel):
    """Candidate events for the largest move of an asset in a window."""

    asset: str
    move_pct: float
    move_day: str
    candidates: list[Candidate]
    status: Literal["hypothesis"] = "hypothesis"
    disclaimer: str = DISCLAIMER


class TimelineItem(BaseModel):
    """One day: number of events and the asset's price move."""

    day: str
    events: int | None = None
    close: float | None = None
    ret_1d: float | None = None


class PathItem(BaseModel):
    """A shortest path in the graph."""

    nodes: list[str]
    relations: list[str]
    hops: int


class CentralityItem(BaseModel):
    """A country and its PageRank score."""

    iso3: str
    country: str | None = None
    score: float
