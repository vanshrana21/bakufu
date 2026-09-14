"""Raster feature extraction and spectral index tests.

These run against the smoke-test rasters and need no database.
"""

from __future__ import annotations

import pandas as pd
import pytest

from src.config.settings import settings
from src.data.preprocess.compute_indices import INDEX_COLUMNS, add_indices
from src.data.preprocess.extract_features import (
    BAND_FEATURES,
    FEATURE_COLUMNS,
    extract_features_at_point,
    extract_features_bulk,
)

pytestmark = pytest.mark.skipif(
    not (settings.s2_smoke_test.exists() and settings.dem_smoke_test.exists()),
    reason="smoke-test rasters not present",
)

# Inside the Sausar belt bbox, on the Balaghat side of the scene.
BALAGHAT_LON, BALAGHAT_LAT = 80.445098, 21.967274
# Well outside the scene (Arabian Sea, off Mumbai).
OUTSIDE_LON, OUTSIDE_LAT = 72.0, 19.0


def test_extract_features_at_balaghat_returns_valid_bands() -> None:
    features = extract_features_at_point(BALAGHAT_LON, BALAGHAT_LAT)

    assert features is not None
    assert set(FEATURE_COLUMNS).issubset(features)

    for band in BAND_FEATURES:
        value = features[band]
        assert value is not None, f"{band} was None inside the scene"
        assert 0 < value < 20000, f"{band}={value} outside plausible S2 DN range"

    assert 200 < features["elevation"] < 1200
    assert 0 <= features["slope"] <= 90
    assert 0 <= features["aspect"] <= 360


def test_extract_features_outside_bbox_returns_none() -> None:
    assert extract_features_at_point(OUTSIDE_LON, OUTSIDE_LAT) is None


def test_extract_features_bulk_matches_point_extraction() -> None:
    frame = pd.DataFrame(
        [
            {"lon": BALAGHAT_LON, "lat": BALAGHAT_LAT},
            {"lon": OUTSIDE_LON, "lat": OUTSIDE_LAT},
        ]
    )
    out = extract_features_bulk(frame)

    assert len(out) == 2
    assert set(FEATURE_COLUMNS).issubset(out.columns)

    point = extract_features_at_point(BALAGHAT_LON, BALAGHAT_LAT)
    assert point is not None
    for band in BAND_FEATURES:
        assert out.loc[0, band] == pytest.approx(point[band])
        assert pd.isna(out.loc[1, band]), "outside point should have NaN bands"


def test_indices_computed_within_expected_ranges() -> None:
    frame = pd.DataFrame([{"lon": BALAGHAT_LON, "lat": BALAGHAT_LAT}])
    out = add_indices(extract_features_bulk(frame))

    assert set(INDEX_COLUMNS).issubset(out.columns)
    row = out.iloc[0]

    assert -1.0 <= row["ndvi"] <= 1.0
    assert -1.0 <= row["normalised_burn_ratio_swir"] <= 1.0
    assert row["mn_ratio_swir"] > 0
    assert row["iron_ratio"] > 0
    # ferrous_ratio (B11/B08) must stay distinct from mn_ratio_swir (B11/B12);
    # they were accidentally the same ratio until Phase 2.9.
    assert row["ferrous_ratio"] == pytest.approx(row["b11"] / row["b08"])
    assert row["ferrous_ratio"] != pytest.approx(row["mn_ratio_swir"])


def test_indices_require_band_columns() -> None:
    with pytest.raises(KeyError):
        add_indices(pd.DataFrame([{"lon": 0.0, "lat": 0.0}]))
