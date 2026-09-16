"""API endpoint tests.

The health check needs no database; the data endpoints are skipped without one.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.conftest import requires_db


def test_health_check(api_client: TestClient) -> None:
    response = api_client.get("/")
    assert response.status_code == 200
    from src.api.main import API_VERSION

    # Assert against the constant rather than a literal: adding Phase 4
    # endpoints bumped the version, and the health *shape* is what matters.
    body = response.json()
    assert set(body) == {
        "status", "version", "model_version", "model_source", "encoder_version",
        "provenance_bound", "degraded",
    }
    assert body["status"] == "ok" and body["version"] == API_VERSION
    assert body["degraded"] == []
    # Says which bundle is being scored with, and where that decision came from.
    assert body["model_source"] in {"registry", "env", "shipped"}
    assert body["model_version"]
    # The encoder defines the feature space the model scores, so it is reported
    # alongside it rather than folded into the model version.
    assert body["encoder_version"]
    # Whether the served bundle records the inputs it was trained on. False on
    # the shipped model, which predates provenance binding - stated rather than
    # inferred, so an unverifiable pairing never looks like a checked one.
    assert isinstance(body["provenance_bound"], bool)


@requires_db
def test_boreholes_list_returns_46(api_client: TestClient) -> None:
    response = api_client.get("/boreholes")
    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 46
    assert {"id", "nuid", "borehole_no", "lat", "lon"}.issubset(payload[0])


@requires_db
def test_borehole_detail(api_client: TestClient) -> None:
    first_id = api_client.get("/boreholes").json()[0]["id"]

    response = api_client.get(f"/boreholes/{first_id}")
    assert response.status_code == 200

    borehole = response.json()
    assert borehole["id"] == first_id
    assert borehole["commodity"] == "Manganese"
    assert 21.0 < borehole["lat"] < 22.5
    assert 78.5 < borehole["lon"] < 81.0


@requires_db
def test_borehole_detail_404(api_client: TestClient) -> None:
    assert api_client.get("/boreholes/99999999").status_code == 404


@requires_db
def test_borehole_features(api_client: TestClient) -> None:
    first_id = api_client.get("/boreholes").json()[0]["id"]

    response = api_client.get(f"/boreholes/{first_id}/features")
    assert response.status_code == 200

    features = response.json()["features"]
    assert features["b11"] is not None
    assert features["elevation"] is not None
    assert -1.0 <= features["ndvi"] <= 1.0


@requires_db
def test_priors_list_returns_7(api_client: TestClient) -> None:
    response = api_client.get("/priors")
    assert response.status_code == 200
    assert len(response.json()) == 7


@requires_db
def test_foreign_pagination(api_client: TestClient) -> None:
    response = api_client.get("/foreign", params={"page_size": 25})
    assert response.status_code == 200

    page = response.json()
    assert page["page"] == 1
    assert page["page_size"] == 25
    assert page["total"] > 1000
    assert len(page["items"]) == 25
