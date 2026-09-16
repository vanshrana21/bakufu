"""A stored prediction must be able to reproduce the response it came from.

The audit row used to carry a score, a deposit type and a model version. That
is not enough to reconstruct anything: it did not say WHERE it was scored, which
mask produced the number, what the score was before the mask, or which encoder
supplied 64 of the model's features. Each of those changes the result, so a row
missing them is a record of an answer nobody can check.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from geoalchemy2.shape import from_shape
from shapely.geometry import box

from src.api.routers.predictions import _CELL_HALF_DEG, _cell_centre
from src.api.schemas import PredictionRecordOut
from tests.conftest import requires_db

LAT, LON = 21.7134, 79.8221


def _cell(lat: float, lon: float):
    return from_shape(
        box(lon - _CELL_HALF_DEG, lat - _CELL_HALF_DEG, lon + _CELL_HALF_DEG, lat + _CELL_HALF_DEG),
        srid=4326,
    )


# --- the geometry a row stores identifies the point that was scored ------


def test_the_cell_centre_is_the_point_that_was_requested() -> None:
    centre = _cell_centre(_cell(LAT, LON))
    assert centre is not None
    lat, lon = centre
    # The cell is ~60 m across; its centre is the request to well under a metre.
    assert lat == pytest.approx(LAT, abs=1e-9)
    assert lon == pytest.approx(LON, abs=1e-9)


def test_an_unreadable_geometry_degrades_to_unknown_rather_than_failing() -> None:
    """The score and model identity are still a usable audit record without it."""
    assert _cell_centre(object()) is None
    assert _cell_centre(None) is None


# --- the response schema carries every field needed to reproduce ---------


def test_the_record_schema_exposes_the_full_scoring_context() -> None:
    fields = set(PredictionRecordOut.model_fields)
    for required in [
        "prospectivity_score",
        "model_version",
        "encoder_version",
        "mask_applied",
        "raw_score",
        "final_score",
        "lat",
        "lon",
        "created_at",
    ]:
        assert required in fields, f"PredictionRecordOut cannot reproduce a score without {required}"


def test_missing_optional_context_stays_null_rather_than_defaulting() -> None:
    """A row written before these columns existed does not know its encoder.
    Reporting today's fingerprint would state something nobody verified."""
    record = PredictionRecordOut(
        id=1,
        prospectivity_score=0.5,
        deposit_type="SEDIMENTARY",
        model_version="prospectivity_v6",
        created_at="2026-09-16T10:00:00Z",
    )
    assert record.encoder_version is None
    assert record.lat is None and record.lon is None
    assert record.raw_score is None and record.final_score is None


# --- end to end, against the real database -------------------------------


@requires_db
def test_a_scored_point_can_be_read_back_with_its_full_context(
    api_client: TestClient,
) -> None:
    response = api_client.post("/predict/point?mask=none", json={"lat": LAT, "lon": LON})
    if response.status_code == 404:
        pytest.skip("point lies outside the imagery footprint in this checkout")
    if response.status_code == 503:
        pytest.skip("prospectivity model is not available in this checkout")
    assert response.status_code == 200, response.text
    scored = response.json()

    prediction_id = scored["prediction_id"]
    if prediction_id is None:
        pytest.skip("database not reachable, so no audit row was written")

    stored = api_client.get(f"/predictions/{prediction_id}")
    assert stored.status_code == 200, stored.text
    row = stored.json()

    # Same answer, same model, same place.
    assert row["final_score"] == pytest.approx(scored["final_score"])
    assert row["raw_score"] == pytest.approx(scored["raw_score"])
    assert row["mask_applied"] == scored["mask_applied"]
    assert row["model_version"] == scored["model_version"]
    assert row["lat"] == pytest.approx(LAT, abs=1e-6)
    assert row["lon"] == pytest.approx(LON, abs=1e-6)

    # And it says which encoder produced the latent features.
    health = api_client.get("/").json()
    assert row["encoder_version"] == health["encoder_version"]


@requires_db
def test_a_masked_out_point_still_records_the_score_it_would_have_had(
    api_client: TestClient,
) -> None:
    """final_score 0 with raw_score preserved is the whole point of the pair."""
    response = api_client.post("/predict/point?mask=both", json={"lat": LAT, "lon": LON})
    if response.status_code in (404, 503):
        pytest.skip("point unavailable in this checkout")
    body = response.json()
    if body["prediction_id"] is None:
        pytest.skip("database not reachable")

    row = api_client.get(f"/predictions/{body['prediction_id']}").json()
    assert row["mask_applied"] == "both"
    assert row["raw_score"] is not None
    if body["final_score"] == 0.0:
        assert row["final_score"] == 0.0
        assert row["raw_score"] > 0.0, "a masked-out cell must stay inspectable"
