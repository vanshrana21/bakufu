"""The optional X-API-Key gate in src/api/security.py."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from src.api.main import app
from src.config.settings import settings

KEY = "test-key-7f3a"


@pytest.fixture()
def client() -> Iterator[TestClient]:
    # No lifespan: the gate runs before any route touches an artifact.
    yield TestClient(app)


@pytest.fixture()
def keyed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "API_KEY", KEY)


def test_open_when_no_key_is_configured(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "API_KEY", "")
    assert client.get("/masks").status_code == 200


@pytest.mark.usefixtures("keyed")
def test_missing_key_is_rejected_with_the_error_contract(client: TestClient) -> None:
    response = client.get("/masks")
    assert response.status_code == 401
    body = response.json()
    assert body["error_code"] == "unauthorized"
    assert "X-API-Key" in body["remedy"]


@pytest.mark.usefixtures("keyed")
def test_wrong_key_is_rejected(client: TestClient) -> None:
    assert client.get("/masks", headers={"X-API-Key": "nope"}).status_code == 401


@pytest.mark.usefixtures("keyed")
def test_correct_key_is_accepted(client: TestClient) -> None:
    assert client.get("/masks", headers={"X-API-Key": KEY}).status_code == 200


@pytest.mark.usefixtures("keyed")
def test_post_routes_are_gated_too(client: TestClient) -> None:
    response = client.post("/predict/point", json={"lat": 21.7, "lon": 79.8})
    assert response.status_code == 401


@pytest.mark.usefixtures("keyed")
def test_health_check_stays_open(client: TestClient) -> None:
    assert client.get("/").status_code == 200


@pytest.mark.usefixtures("keyed")
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


@pytest.mark.usefixtures("keyed")
def test_rejection_still_carries_cors_headers(client: TestClient) -> None:
    """A browser must be able to read the 401 body instead of seeing a CORS error."""
    response = client.get("/masks", headers={"Origin": "http://localhost:3000"})
    assert response.status_code == 401
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_openapi_documents_the_key_header(client: TestClient) -> None:
    schemes = client.get("/openapi.json").json()["components"]["securitySchemes"]
    assert any(scheme.get("name") == "X-API-Key" for scheme in schemes.values())
