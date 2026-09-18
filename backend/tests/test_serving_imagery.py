"""Serving imagery: the right mosaic, and no scores without real pixels.

Until 2026-09-13 the API scored from s2_nagpur_smoke_test.tif while v6 was
trained on s2_sausar_v2.tif. The smoke mosaic's gaps are zeros with no nodata
declared, so about a quarter of the warm heatmap was scored from blank pixels,
and blank national-tile patches returned scores at Kandri and Beldongri.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.config.settings import settings
from src.data.preprocess.extract_features import BAND_FEATURES

requires_serving_rasters = pytest.mark.skipif(
    not (settings.S2_SERVING_PATH.exists() and settings.DEM_SERVING_PATH.exists()),
    reason="operational rasters missing - run python -m src.data.ingest.fetch_gumgaon_strip",
)

#: Old settings coordinate for Kandri: covered by Nagpur_1.tif's extent, but
#: every pixel there is zero.
BLANK_PATCH = (21.2667, 79.0)
#: Gumgaon's reported location, 0.9 km west of the training mosaic's edge.
GUMGAON = (21.400, 78.980)


def test_has_imagery_rejects_zero_and_missing_bands() -> None:
    from src.models.prospectivity.predict import has_imagery

    real = dict.fromkeys(BAND_FEATURES, 1200.0)
    frame = pd.DataFrame(
        [
            real,
            dict.fromkeys(BAND_FEATURES, 0.0),  # composite gap
            {**real, "b02": 0.0},  # one empty band is still a gap
            dict.fromkeys(BAND_FEATURES, None),  # outside the raster
            {**real, "b12": None},
        ]
    )
    assert has_imagery(frame).tolist() == [True, False, False, False, False]


def test_serving_defaults_to_the_operational_mosaic() -> None:
    """Not the smoke-test mosaic the API silently fell back to before."""
    from src.models.prospectivity.predict import ACTIVE_DEM_PATH, ACTIVE_S2_PATH

    assert ACTIVE_S2_PATH.name == "s2_moil_operational_v1.tif"
    assert ACTIVE_DEM_PATH.name == "dem_moil_operational.tif"
    assert settings.S2_TRAINING_PATH.name == "s2_sausar_v2.tif"


@requires_serving_rasters
def test_operational_mosaic_serves_training_pixels_unchanged() -> None:
    """Every location v6 was trained on must read identically at serving time."""
    import rasterio
    from pyproj import Transformer

    rng = np.random.default_rng(13)
    with rasterio.open(settings.S2_TRAINING_PATH) as training, rasterio.open(
        settings.S2_SERVING_PATH
    ) as serving:
        left, bottom, right, top = training.bounds
        xs = rng.uniform(left + 40, right - 40, 300)
        ys = rng.uniform(bottom + 40, top - 40, 300)
        points = list(zip(xs, ys))
        assert serving.crs == training.crs
        assert np.array_equal(
            np.array(list(training.sample(points))), np.array(list(serving.sample(points)))
        )
        # And it extends west, which is the point of the operational mosaic.
        lon_edge, _ = Transformer.from_crs(serving.crs, "EPSG:4326", always_xy=True).transform(
            serving.bounds.left, (serving.bounds.bottom + serving.bounds.top) / 2
        )
        assert lon_edge < GUMGAON[1]


@requires_serving_rasters
def test_predict_at_blank_patch_returns_none() -> None:
    from src.models.prospectivity.predict import predict_point

    assert predict_point(*BLANK_PATCH, explain=False) is None


@requires_serving_rasters
def test_predict_at_blank_patch_returns_404(api_client) -> None:
    lat, lon = BLANK_PATCH
    response = api_client.post("/predict/point", json={"lat": lat, "lon": lon})
    assert response.status_code == 404
    body = response.json()
    assert body["error_code"] == "no_imagery_at_location"
    assert body["detail"] == f"Sentinel-2 mosaic does not cover ({lat}, {lon})"
    assert "/prospectivity/heatmap" in body["remedy"]


@requires_serving_rasters
def test_heatmap_null_for_no_imagery() -> None:
    """Cells over blank patches are null, never a low score."""
    from src.models.prospectivity.predict import heatmap_grid

    grid = heatmap_grid(78.95, 21.20, 79.05, 21.28, grid_size=8)
    flat = [value for row in grid["scores"] for value in row]
    assert all(value is None for value in flat), "blank tile pixels were scored"
    assert grid["cells"]["cells_outside_raster"] == 64
    assert grid["score_range"]["min"] is None


@requires_serving_rasters
def test_gumgaon_scoreable_after_western_strip() -> None:
    """Gumgaon returned 404 before the strip; it now has real imagery."""
    from src.models.prospectivity.predict import predict_point

    result = predict_point(*GUMGAON, explain=False)
    assert result is not None
    extracted = result["features_extracted"]
    assert all(extracted[band] not in (None, 0.0) for band in BAND_FEATURES)
    assert extracted["elevation"] is not None
    assert 0.0 <= result["prospectivity_score"] <= 0.99


@requires_serving_rasters
def test_west_of_the_strip_still_has_no_imagery() -> None:
    """The strip covers Gumgaon, not the whole western margin."""
    from src.models.prospectivity.predict import predict_point

    assert predict_point(21.40, 78.90, explain=False) is None
