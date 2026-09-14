"""Error types and the flat 500 body the contract documents.

Validation errors stay on FastAPI's native 422 shape - there is deliberately
no 400 - so the frontend needs one handler for "user input rejected". Server
-side failures use the flat body below, carrying a machine-readable code.
"""

from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse


class ApiError(Exception):
    """A server-side failure the client should see a code for."""

    status_code = 500
    error_code = "internal_error"

    def __init__(self, detail: str, remedy: str | None = None) -> None:
        super().__init__(detail)
        self.detail = detail
        self.remedy = remedy


class ModelNotLoaded(ApiError):
    error_code = "model_not_loaded"

    def __init__(self, filename: str, reason: str) -> None:
        super().__init__(
            detail=f"{filename} could not be loaded: {reason}",
            remedy=(
                "check the artifact exists in models/ or data/processed/, then "
                "restart the API so the lifespan handler reloads it"
            ),
        )


class DataNotLoaded(ApiError):
    error_code = "data_not_loaded"


class PredictionFailed(ApiError):
    error_code = "prediction_failed"


class NotImplementedInDemo(ApiError):
    status_code = 501
    error_code = "not_implemented"


async def api_error_handler(_request: Request, exc: ApiError) -> JSONResponse:
    body: dict[str, str] = {"error_code": exc.error_code, "detail": exc.detail}
    if exc.remedy:
        body["remedy"] = exc.remedy
    return JSONResponse(status_code=exc.status_code, content=body)
