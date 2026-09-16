"""The fail-closed X-API-Key gate: ServerSettings and src/api/security.py.

There is no open mode. The server refuses to start without API_KEY, and every
route - the health check included - answers 401 without the exact key.
"""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from src.api.main import app
from src.api.security import API_KEY_HEADER
from src.config.settings import PROJECT_ROOT, ServerSettings, get_server_settings

KEY = "test-key-7f3a"


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setattr(get_server_settings(), "API_KEY", SecretStr(KEY))
    # No lifespan: the gate runs before any route touches an artifact.
    yield TestClient(app)


# --- the server refuses to start without a key --------------------------


@pytest.mark.parametrize("value", [None, "", "   "])
def test_a_missing_or_blank_api_key_is_fatal(monkeypatch: pytest.MonkeyPatch, value: str | None) -> None:
    if value is None:
        monkeypatch.delenv("API_KEY", raising=False)
    else:
        monkeypatch.setenv("API_KEY", value)
    # ValidationError is a ValueError; _env_file=None keeps the real .env out.
    with pytest.raises(ValueError, match="API_KEY is missing or empty"):
        ServerSettings(_env_file=None)


def test_a_configured_key_is_accepted(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("API_KEY", KEY)
    configured = ServerSettings(_env_file=None).API_KEY
    assert configured is not None and configured.get_secret_value() == KEY


def test_importing_the_app_without_a_key_fails() -> None:
    """uvicorn imports src.api.main:app - that import is what must fail."""
    result = subprocess.run(
        [sys.executable, "-c", "import src.api.main"],
        cwd=PROJECT_ROOT,
        env={"PATH": "/usr/bin:/bin", "API_KEY": "", "HOME": "/tmp", "OMP_NUM_THREADS": "1"},
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert result.returncode != 0
    assert "API_KEY is missing or empty" in result.stderr


# --- every route is gated -----------------------------------------------


def test_missing_key_is_rejected_with_the_error_contract(client: TestClient) -> None:
    response = client.get("/masks")
    assert response.status_code == 401
    body = response.json()
    assert body["error_code"] == "unauthorized"
    assert API_KEY_HEADER in body["remedy"]


def test_wrong_key_is_rejected(client: TestClient) -> None:
    assert client.get("/masks", headers={API_KEY_HEADER: "nope"}).status_code == 401


def test_empty_key_is_rejected(client: TestClient) -> None:
    assert client.get("/masks", headers={API_KEY_HEADER: ""}).status_code == 401


def test_a_non_ascii_key_is_rejected_rather_than_crashing(client: TestClient) -> None:
    """compare_digest raises TypeError on non-ASCII str; bytes keep this a 401."""
    assert client.get("/masks", headers={API_KEY_HEADER: "clé-🙂".encode()}).status_code == 401


def test_correct_key_is_accepted(client: TestClient) -> None:
    assert client.get("/masks", headers={API_KEY_HEADER: KEY}).status_code == 200


def test_post_routes_are_gated_too(client: TestClient) -> None:
    response = client.post("/predict/point", json={"lat": 21.7, "lon": 79.8})
    assert response.status_code == 401


def test_the_health_check_is_gated_too(client: TestClient) -> None:
    assert client.get("/").status_code == 401
    assert client.get("/", headers={API_KEY_HEADER: KEY}).status_code == 200


def test_a_blank_server_key_lets_nothing_through(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """Defence in depth: even a key blanked at runtime opens nothing."""
    monkeypatch.setattr(get_server_settings(), "API_KEY", SecretStr(""))
    assert client.get("/masks").status_code == 401
    assert client.get("/masks", headers={API_KEY_HEADER: ""}).status_code == 401
    assert client.get("/masks", headers={API_KEY_HEADER: KEY}).status_code == 401


def test_cors_preflight_is_answered_without_a_key(client: TestClient) -> None:
    response = client.options(
        "/predict/point",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type,x-api-key",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_rejection_still_carries_cors_headers(client: TestClient) -> None:
    """A browser must be able to read the 401 body instead of seeing a CORS error."""
    response = client.get("/masks", headers={"Origin": "http://localhost:3000"})
    assert response.status_code == 401
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_openapi_documents_the_key_header(client: TestClient) -> None:
    schemes = client.get("/openapi.json").json()["components"]["securitySchemes"]
    assert any(scheme.get("name") == API_KEY_HEADER for scheme in schemes.values())
