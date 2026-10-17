"""API key check for the sensitive endpoint POST /api/ask (header X-API-Key, value from API_KEY in .env)."""

import secrets
from typing import Annotated

from fastapi import Depends, HTTPException, Security
from fastapi.security import APIKeyHeader

from app.config import Settings, get_settings

api_key_header = APIKeyHeader(
    name="X-API-Key",
    auto_error=False,
    description="Required on POST /api/ask. The value is API_KEY from the server's .env.",
)


def require_api_key(
    key: Annotated[str | None, Security(api_key_header)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    """Reject the request unless X-API-Key matches API_KEY; fail closed when the server has no key."""
    if not settings.api_key:
        raise HTTPException(status_code=503, detail="API key not configured on the server: set API_KEY in .env")
    if not key or not secrets.compare_digest(key.encode(), settings.api_key.encode()):
        raise HTTPException(
            status_code=401,
            detail="Missing or invalid API key: send it in the X-API-Key header",
            headers={"WWW-Authenticate": "APIKey"},
        )
