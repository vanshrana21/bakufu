"""Tests for the geological and occurrence-buffer prediction masks."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.config.settings import settings
from src.data.masks.geological_mask import MASK_PATH, GeologicalMask
from src.data.masks.occurrence_buffer_mask import (
    OUT_PATH as BUFFER_PATH,
)
from src.data.masks.occurrence_buffer_mask import (
    OccurrenceBufferMask,
    build_occurrence_buffer_mask,
)
from src.data.masks.registry import VALID_MASKS, apply_mask, describe

#: Coordinates reused across the Phase 2.9 diagnostics.
UKWA = (21.71, 79.79)
KATORI = (21.58, 79.86)
FARMLAND = (21.55, 79.30)
NAGPUR_CITY = (21.15, 79.09)


@pytest.fixture(scope="module")
def geological() -> GeologicalMask:
    if not MASK_PATH.exists():
        pytest.skip(f"geological mask not built: {MASK_PATH}")
    return GeologicalMask()


@pytest.fixture(scope="module")
def buffer_mask() -> OccurrenceBufferMask:
    if not BUFFER_PATH.exists():
        pytest.skip(f"occurrence buffer not built: {BUFFER_PATH}")
    return OccurrenceBufferMask()


def test_geological_mask_loads(geological: GeologicalMask) -> None:
    assert len(geological) > 0
    assert geological.gdf.crs.to_epsg() == 4326
    assert geological.formations()


def test_occurrence_buffer_mask_generates(tmp_path: Path) -> None:
    out = tmp_path / "buffer.geojson"
    gdf = build_occurrence_buffer_mask(buffer_km=5.0, output_path=out, verbose=False)
    assert out.exists()
    assert len(gdf) == 1
    assert int(gdf.n_points.iloc[0]) > 100
    assert float(gdf.buffer_km.iloc[0]) == pytest.approx(5.0)
    assert gdf.geometry.iloc[0].is_valid


def test_buffer_is_union_not_hull(buffer_mask: OccurrenceBufferMask) -> None:
    """A union of per-point buffers must be smaller than its own convex hull.

    This is what separates "within 5 km of an occurrence" from a hull, which
    fills its interior and would swallow ground far from any occurrence.
    """
    geom = buffer_mask.mask_geom
    assert geom.area < geom.convex_hull.area


def test_ukwa_inside_geological(geological: GeologicalMask) -> None:
    assert geological.is_in_basement(*UKWA)


def test_ukwa_inside_buffer(buffer_mask: OccurrenceBufferMask) -> None:
    """Ukwa is 2.38 km from a confirmed occurrence."""
    assert buffer_mask.is_in_buffer(*UKWA)


def test_katori_inside_buffer(buffer_mask: OccurrenceBufferMask) -> None:
    """Katori is 0.11 km from a confirmed occurrence."""
    assert buffer_mask.is_in_buffer(*KATORI)


def test_nagpur_city_outside_buffer(buffer_mask: OccurrenceBufferMask) -> None:
    """Nagpur city is ~26 km from the nearest confirmed occurrence."""
    assert not buffer_mask.is_in_buffer(*NAGPUR_CITY)


def test_farmland_outside_buffer(buffer_mask: OccurrenceBufferMask) -> None:
    """The farmland false positive is 7.21 km out, so a 5 km buffer excludes it.

    At the previous 10 km radius it survived; this test pins the radius that
    makes the mask do its job.
    """
    assert not buffer_mask.is_in_buffer(*FARMLAND)


def test_farmland_masked_by_buffer_5km() -> None:
    score, decision = apply_mask(*FARMLAND, 0.99, "occurrence_buffer")
    assert score == 0.0
    assert decision == "masked_out_outside_buffer"


def test_registry_modes_are_known() -> None:
    assert set(VALID_MASKS) == {"none", "geological", "occurrence_buffer", "both"}
    ids = {entry["id"] for entry in describe()}
    assert ids == set(VALID_MASKS)


def test_apply_mask_none_is_passthrough() -> None:
    score, decision = apply_mask(*NAGPUR_CITY, 0.87, "none")
    assert score == pytest.approx(0.87)
    assert decision == "n/a"


def test_apply_mask_rejects_unknown_mode() -> None:
    with pytest.raises(ValueError, match="unknown mask"):
        apply_mask(*UKWA, 0.5, "not_a_mask")


def test_both_stacked_masks_ukwa_kept() -> None:
    score, decision = apply_mask(*UKWA, 0.88, "both")
    assert score == pytest.approx(0.88)
    assert decision == "kept_in_basement_and_buffer"


def test_both_stacked_masks_katori_kept() -> None:
    score, decision = apply_mask(*KATORI, 0.99, "both")
    assert score == pytest.approx(0.99)
    assert decision == "kept_in_basement_and_buffer"


def test_both_stacked_farmland_filtered() -> None:
    """The stack now removes the farmland false positive.

    The geological mask alone keeps it (87% of the bbox is Precambrian at
    1:5M); the 5 km buffer is what does the work.
    """
    score, decision = apply_mask(*FARMLAND, 0.99, "both")
    assert score == 0.0
    assert decision == "masked_out_both"

    kept, kept_decision = apply_mask(*FARMLAND, 0.99, "geological")
    assert kept == pytest.approx(0.99)
    assert kept_decision == "kept_in_basement"


def test_frontend_metadata_matches_registry() -> None:
    import json

    path = settings.DATA_PROCESSED / "frontend_mask_metadata.json"
    if not path.exists():
        pytest.skip("frontend metadata not generated")
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert {m["id"] for m in payload["masks"]} == set(VALID_MASKS)


def test_predict_endpoint_with_mask_param() -> None:
    """/predict/point accepts ?mask= and reports what it did."""
    from fastapi.testclient import TestClient

    from src.api.main import app

    if not (settings.MODELS_DIR / "prospectivity_v1.pkl").exists():
        pytest.skip("no trained model available")

    with TestClient(app) as client:
        response = client.get("/masks")
        assert response.status_code == 200
        assert {entry["id"] for entry in response.json()} == set(VALID_MASKS)

        bad = client.post(
            "/predict/point", json={"lat": 21.71, "lon": 79.79}, params={"mask": "nope"}
        )
        assert bad.status_code == 422
