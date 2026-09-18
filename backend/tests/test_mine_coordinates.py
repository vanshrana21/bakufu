"""MOIL mine coordinates: provenance, consistency, and that each one scores.

Coordinates were reconciled on 2026-09-13 from docs/moil_coordinate_sources.md.
They live in settings.MOIL_MINES; equipment and fleet data stay in
src/reference/moil_mines.py, so these tests also stop the two drifting apart.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.api.main import app
from src.config import settings as settings_module
from src.config.settings import get_verified_mines, settings
from src.data.preprocess.extract_features import BAND_FEATURES
from src.reference.moil_mines import MOIL_MINES as REFERENCE_MINES
from src.reference.moil_mines import OPENCAST_FLEET_VOCAB

CONFIDENCE_TIERS = {"high", "medium_high", "low_medium", "low", "none"}
COORDINATE_KEYS = {
    "lat", "lon", "state", "district", "type", "confidence",
    "source", "source_url", "coordinate_precision", "note",
}
STATE_CODES = {"MH": "Maharashtra", "MP": "Madhya Pradesh"}

requires_serving_rasters = pytest.mark.skipif(
    not (settings.S2_SERVING_PATH.exists() and settings.DEM_SERVING_PATH.exists()),
    reason="operational rasters missing - run python -m src.data.ingest.fetch_gumgaon_strip",
)


@pytest.fixture(scope="module")
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


# --- the table itself ---------------------------------------------------


def test_all_ten_mines_carry_coordinate_provenance() -> None:
    assert set(settings.MOIL_MINES) == set(REFERENCE_MINES)
    for name, mine in settings.MOIL_MINES.items():
        assert set(mine) == COORDINATE_KEYS, name
        assert mine["confidence"] in CONFIDENCE_TIERS, name
        assert mine["source"], f"{name} has no named source"
        # Inside the Sausar belt study region, not a transposed lat/lon.
        assert 21.0 <= mine["lat"] <= 22.2 and 78.9 <= mine["lon"] <= 80.7, name


def test_source_urls_are_full_or_null_never_truncated() -> None:
    """A truncated link is an unverifiable citation; null is the honest value."""
    for name, mine in settings.MOIL_MINES.items():
        url = mine["source_url"]
        if url is None:
            continue
        assert url.startswith("https://"), name
        assert "..." not in url and "…" not in url, f"{name}: truncated URL {url}"


def test_coordinate_table_agrees_with_the_reference_module() -> None:
    """State, district and type must not drift between the two mine tables."""
    for name, mine in settings.MOIL_MINES.items():
        reference = REFERENCE_MINES[name]
        assert mine["state"] == STATE_CODES[reference["state"]], name
        assert mine["district"] == reference["district"], name
        assert mine["type"] == reference["mine_type"], name


def test_unverified_types_are_not_changed() -> None:
    """The submission called these underground on Wikipedia proxies only."""
    assert settings.MOIL_MINES["Tirodi"]["type"] == "opencast"
    assert settings.MOIL_MINES["Dongri Buzurg"]["type"] == "opencast"


def test_sitapatore_uses_the_mining_plan_point() -> None:
    sitapatore = settings.MOIL_MINES["Sitapatore"]
    assert (sitapatore["lat"], sitapatore["lon"]) == (21.7000, 79.6667)
    assert sitapatore["state"] == "Madhya Pradesh"
    assert sitapatore["district"] == "Balaghat"
    assert sitapatore["type"] == "opencast"
    assert sitapatore["source_url"] == (
        "https://forestsclearance.nic.in/DownloadPdfFile.aspx?"
        "FileName=611712291216JLTFUMiningplan.pdf"
    )


def test_get_verified_mines_excludes_unlocated_coordinates(monkeypatch) -> None:
    assert set(get_verified_mines()) == set(settings.MOIL_MINES), "no mine is unlocated today"
    unlocated = {**settings.MOIL_MINES["Beldongri"], "confidence": "none"}
    monkeypatch.setitem(settings_module.MOIL_MINES, "Placeholder", unlocated)
    assert "Placeholder" not in get_verified_mines()
    assert "Beldongri" in get_verified_mines()


# --- /mines -------------------------------------------------------------


def test_mines_endpoint_serves_coordinate_provenance(client: TestClient) -> None:
    for mine in client.get("/mines").json()["mines"]:
        expected = settings.MOIL_MINES[mine["mine_name"]]
        for key in ("lat", "lon", "confidence", "source", "source_url", "coordinate_precision"):
            assert mine[key] == expected[key], (mine["mine_name"], key)


@pytest.mark.parametrize("name", ["Beldongri", "Dongri Buzurg", "Tirodi"])
def test_weak_coordinates_carry_a_note(client: TestClient, name: str) -> None:
    body = client.get(f"/mines/{name}").json()
    assert body["coordinate_note"], f"{name} is low confidence or approximate"
    assert "approximate" in body["coordinate_note"].lower()


def test_strong_coordinates_have_no_generated_note(client: TestClient) -> None:
    assert client.get("/mines/Ukwa").json()["coordinate_note"] is None


def test_source_notes_pass_through(client: TestClient) -> None:
    assert "different village" in client.get("/mines/Kandri").json()["coordinate_note"]
    assert "Sukli" in client.get("/mines/Sitapatore").json()["coordinate_note"]


def test_mine_state_counts_reflect_sitapatore_in_madhya_pradesh(client: TestClient) -> None:
    counts = client.get("/mines").json()["counts"]
    assert counts["MP"] == 4 and counts["MH"] == 6
    assert client.get("/mines/Sitapatore").json()["state"] == "MP"


# --- downstream ---------------------------------------------------------


def test_sitapatore_recommendations_use_opencast_vocabulary(client: TestClient) -> None:
    """A real historical shortfall replayed for Sitapatore gets opencast rules."""
    body = client.get(
        "/recommendations/scenario/2021-04", params={"mine_name": "Sitapatore"}
    ).json()
    assert body["recommendations"], "p=0.91 month should produce cards"
    equipment = {item for card in body["recommendations"] for item in card["equipment_referenced"]}
    assert equipment, "cards should name equipment"
    assert equipment <= set(OPENCAST_FLEET_VOCAB), equipment


@requires_serving_rasters
@pytest.mark.parametrize("name", sorted(get_verified_mines()))
def test_all_verified_mines_return_valid_scores(name: str) -> None:
    """Every verified coordinate has real imagery and a score, not a 404."""
    from src.models.prospectivity.predict import predict_point

    mine = settings.MOIL_MINES[name]
    result = predict_point(mine["lat"], mine["lon"], explain=False)
    assert result is not None, f"{name} ({mine['lat']}, {mine['lon']}) has no imagery"
    extracted = result["features_extracted"]
    assert all(extracted[band] not in (None, 0.0) for band in BAND_FEATURES), name
    assert extracted["elevation"] is not None, name
    assert 0.0 <= result["prospectivity_score"] <= 0.99, name
