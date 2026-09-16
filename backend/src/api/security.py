"""Shared-key protection for the API. Fails closed.

The server cannot start without API_KEY (ServerSettings), and every route - the
health check included - answers 401 unless the request's X-API-Key header holds
exactly that key, compared in constant time. There is no open mode.

Applied to the whole app as a dependency rather than a middleware so the scheme
appears in the OpenAPI document and /docs can send the key. CORS preflights
never reach this: the CORS middleware answers them before routing.
"""

from __future__ import annotations

import hmac

from fastapi import Security
from fastapi.security import APIKeyHeader

from src.api.errors import ApiError
from src.config.settings import get_server_settings

API_KEY_HEADER = "X-API-Key"

_api_key_header = APIKeyHeader(
    name=API_KEY_HEADER,
    auto_error=False,
    description="Required on every route: the server's API_KEY.",
)


class Unauthorized(ApiError):
    status_code = 401
    error_code = "unauthorized"


def require_api_key(key: str | None = Security(_api_key_header)) -> None:
    """Reject the request unless it carries exactly the server's key."""
    configured = get_server_settings().API_KEY
    expected = configured.get_secret_value().encode("utf-8") if configured is not None else b""
    presented = key.encode("utf-8") if key is not None else b""
    # Bytes, not str: compare_digest raises TypeError on non-ASCII str, which a
    # hostile header value would otherwise turn into a 500.
    if not presented or not hmac.compare_digest(presented, expected):
        raise Unauthorized(
            detail="missing or invalid API key",
            remedy=f"send the server's API_KEY in the {API_KEY_HEADER} header",
        )
