"""Schemas for the health endpoints."""

from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Result of a health probe."""

    status: str
    neo4j: bool | None = None
