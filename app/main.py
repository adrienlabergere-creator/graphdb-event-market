"""FastAPI entry point."""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from neo4j.exceptions import DriverError, Neo4jError

from app.routers import analytics, ask, health

DESCRIPTION = (
    "Graph-backed API linking geopolitical and economic events to market series. "
    "Educational and analytical purposes only: no financial advice and no order execution. "
    "Temporal correlation is never presented as causation."
)

app = FastAPI(title="Event-Market Graph API", version="0.1.0", description=DESCRIPTION)
app.include_router(health.router)
app.include_router(analytics.router)
app.include_router(ask.router)


@app.exception_handler(DriverError)
@app.exception_handler(Neo4jError)
async def neo4j_unavailable(_: Request, exc: Exception) -> JSONResponse:
    """Neo4j (or the GDS plugin) cannot answer: HTTP 503 with a readable message."""
    return JSONResponse(status_code=503, content={"detail": f"Neo4j or GDS unavailable: {type(exc).__name__}"})
