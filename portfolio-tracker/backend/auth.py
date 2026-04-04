"""
API key authentication.

All endpoints require the X-API-Key header to match API_SECRET from .env.
If API_SECRET is not set (local dev without the variable), access is open —
this lets docker compose up work out-of-the-box without extra config.

In production (Railway), set API_SECRET to a strong random string and
include it in every request from the frontend.
"""
from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader

from config import settings

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def require_api_key(key: str | None = Security(_api_key_header)) -> None:
    if not settings.api_secret:
        # API_SECRET not configured — allow all (local dev mode)
        return
    if key != settings.api_secret:
        raise HTTPException(status_code=403, detail="Invalid or missing API key")
