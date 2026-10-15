"""Health endpoints used by Docker health checks and the demo."""

from fastapi import APIRouter, HTTPException

from app.database.connection import check_connection
from app.models.health import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Liveness probe: the API process is up."""
    return HealthResponse(status="ok")


@router.get("/health/db", response_model=HealthResponse)
def health_db() -> HealthResponse:
    """Readiness probe: Neo4j answers queries, otherwise HTTP 503."""
    if not check_connection():
        raise HTTPException(status_code=503, detail="Neo4j is unreachable")
    return HealthResponse(status="ok", neo4j=True)
