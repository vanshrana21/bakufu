"""Shared-key protection for the API.

Set API_KEY in .env and every request must carry that key in the X-API-Key
header, compared in constant time. Leave API_KEY blank and the API stays open:
that is the local-development default, and scripts/run_api.py binds 127.0.0.1
so nothing outside this machine can reach it anyway.

Applied to the whole app as a dependency rather than a middleware so the scheme
appears in the OpenAPI document and /docs can send the key. The health check
stays open for liveness probes. CORS preflights never reach this: the CORS
middleware answers them before routing.
"""

from __future__ import annotations

import hmac

from fastapi import Request, Security
from fastapi.security import APIKeyHeader

from src.api.errors import ApiError
from src.config.settings import settings

API_KEY_HEADER = "X-API-Key"

#: Paths served without a key.
OPEN_PATHS: frozenset[str] = frozenset({"/"})

_api_key_header = APIKeyHeader(
    name=API_KEY_HEADER,
    auto_error=False,
    description="Required on every route except the health check when API_KEY is set on the server.",
)


class Unauthorized(ApiError):
    status_code = 401
    error_code = "unauthorized"


def api_key_required() -> bool:
    return bool(settings.API_KEY)


def require_api_key(request: Request, key: str | None = Security(_api_key_header)) -> None:
    """Reject the request unless it carries the configured key."""
    expected = settings.API_KEY
    if not expected or request.url.path in OPEN_PATHS:
        return
    if key is None or not hmac.compare_digest(key.encode("utf-8"), expected.encode("utf-8")):
        raise Unauthorized(
            detail="missing or invalid API key",
            remedy=f"send the server's API_KEY in the {API_KEY_HEADER} header",
        )
