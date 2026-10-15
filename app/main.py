"""FastAPI entry point."""

from fastapi import FastAPI

from app.routers import health

DESCRIPTION = (
    "Graph-backed API linking geopolitical and economic events to market series. "
    "Educational and analytical purposes only: no financial advice and no order execution. "
    "Temporal correlation is never presented as causation."
)

app = FastAPI(title="Event-Market Graph API", version="0.1.0", description=DESCRIPTION)
app.include_router(health.router)
