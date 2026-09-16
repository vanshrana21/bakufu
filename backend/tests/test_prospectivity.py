"""Phase 2 model tests.

These avoid depending on the long training runs: the autoencoder is exercised
untrained, and the classifier tests use the synthetic bundle from conftest.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
import torch

from src.models.prospectivity.autoencoder import (
    BOTTLENECK_DIM,
    N_BANDS,
    PATCH_SIZE,
    MnAutoencoder,
    extract_features,
)
from src.models.prospectivity.enrich_features import AE_COLUMNS
from src.models.prospectivity.pu_xgboost import ALL_FEATURES, BASE_FEATURES


def test_autoencoder_forward_pass() -> None:
    """Reconstruction must come back the same shape as the input patch."""
    model = MnAutoencoder()
    batch = torch.rand(3, N_BANDS, PATCH_SIZE, PATCH_SIZE)

    latent = model.encode(batch)
    reconstruction = model(batch)

    assert latent.shape == (3, BOTTLENECK_DIM)
    assert reconstruction.shape == batch.shape
    assert torch.isfinite(reconstruction).all()


def test_extract_features_returns_bottleneck_dim() -> None:
    """Single patches give (64,); batches give (B, 64)."""
    model = MnAutoencoder()

    single = extract_features(np.random.rand(N_BANDS, PATCH_SIZE, PATCH_SIZE).astype("float32"), model)
    batch = extract_features(torch.rand(5, N_BANDS, PATCH_SIZE, PATCH_SIZE), model)

    assert single.shape == (BOTTLENECK_DIM,)
    assert batch.shape == (5, BOTTLENECK_DIM)


def test_enrich_features_produces_78_dim() -> None:
    """14 base features + 64 autoencoder dims is the Phase 2 feature space."""
    assert len(BASE_FEATURES) == 14
    assert len(AE_COLUMNS) == BOTTLENECK_DIM
    assert len(ALL_FEATURES) == 78
    assert ALL_FEATURES[: len(BASE_FEATURES)] == BASE_FEATURES
    assert len(set(ALL_FEATURES)) == 78  # no duplicated column names


def test_pu_xgboost_trains_without_error(dummy_features: pd.DataFrame) -> None:
    """The configured XGBoost params fit and predict on a tiny frame."""
    from xgboost import XGBClassifier

    from src.models.prospectivity.pu_xgboost import XGB_PARAMS

    rng = np.random.default_rng(7)
    y = rng.integers(0, 2, size=len(dummy_features))
    weights = rng.uniform(0.3, 1.0, size=len(dummy_features))

    model = XGBClassifier(**{**XGB_PARAMS, "n_estimators": 20, "max_depth": 3})
    model.fit(dummy_features, y, sample_weight=weights)
    probabilities = model.predict_proba(dummy_features)[:, 1]

    assert probabilities.shape == (len(dummy_features),)
    assert np.all((probabilities >= 0.0) & (probabilities <= 1.0))


def test_top_k_precision_ranks_correctly() -> None:
    """Perfectly ranked scores give precision 1.0; inverted ranking gives 0.0."""
    from src.models.prospectivity.train_pu_xgboost import top_k_precision

    y = np.array([1, 1, 0, 0, 0])
    assert top_k_precision(y, np.array([0.9, 0.8, 0.2, 0.1, 0.05]), 2) == 1.0
    assert top_k_precision(y, np.array([0.1, 0.2, 0.9, 0.8, 0.7]), 2) == 0.0
    assert top_k_precision(y, np.array([0.9, 0.8, 0.2, 0.1, 0.05]), 99) is None


def test_shap_values_sum_to_prediction(trained_model_path, dummy_features: pd.DataFrame) -> None:
    """SHAP is additive: base_value + sum(shap) must equal the raw margin."""
    from src.models.prospectivity.explain import explain_batch, explain_prediction, load_bundle

    bundle = load_bundle(trained_model_path)
    rows = dummy_features.head(10)

    shap_values = explain_batch(rows, model_path=trained_model_path, make_plot=False)
    margins = bundle["model"].predict(rows, output_margin=True)

    explained = explain_prediction(rows.iloc[0], model_path=trained_model_path)
    base_value = explained["base_value"]

    reconstructed = base_value + shap_values.sum(axis=1)
    assert np.allclose(reconstructed, margins, atol=1e-4)

    # The single-row helper must agree with the model's own probability.
    expected = bundle["model"].predict_proba(rows.head(1))[:, 1][0]
    assert explained["prediction"] == pytest.approx(expected, abs=1e-4)
    assert len(explained["top_5_features"]) == 5


def test_uncertainty_is_highest_at_the_boundary() -> None:
    """Uncertainty peaks at p=0.5 and vanishes at the extremes."""
    from src.models.prospectivity.predict import uncertainty_from_probability

    assert uncertainty_from_probability(0.5) == pytest.approx(1.0)
    assert uncertainty_from_probability(0.0) == pytest.approx(0.0)
    assert uncertainty_from_probability(1.0) == pytest.approx(0.0)
    assert uncertainty_from_probability(0.75) == pytest.approx(0.5)


def test_predict_point_endpoint(api_client, trained_model_path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The endpoint returns the documented response schema."""
    import src.api.routers.predictions as router_module

    payload = {
        "prospectivity_score": 0.73,
        "predicted_type": "unknown",
        "uncertainty": 0.54,
        "features_extracted": {"b02": 0.11, "elevation": 512.0},
        "shap_top5": [{"feature": "b11", "shap_value": 0.42, "actual_value": 0.31}],
        "shap_base_value": -0.18,
        "model_version": "prospectivity_v1",
        "lat": 21.8,
        "lon": 80.2,
    }

    import src.models.prospectivity.predict as predict_module

    monkeypatch.setattr(predict_module, "predict_point", lambda lat, lon, **kw: payload)

    response = api_client.post("/predict/point", json={"lat": 21.8, "lon": 80.2})
    assert response.status_code == 200, response.text

    body = response.json()
    assert 0.0 <= body["prospectivity_score"] <= 1.0
    assert 0.0 <= body["uncertainty"] <= 1.0
    assert body["predicted_type"] in {"sedimentary", "lateritic", "unknown"}
    assert body["shap_top5"][0]["feature"] == "b11"
    assert body["shap_base_value"] == pytest.approx(-0.18)
    assert body["prediction_id"] is not None
    assert router_module is not None


def test_predict_point_rejects_invalid_coordinates(api_client) -> None:
    """Out-of-range latitude is a validation error, not a 500."""
    response = api_client.post("/predict/point", json={"lat": 999.0, "lon": 80.2})
    assert response.status_code == 422


def test_predict_bbox_rejects_inverted_box(api_client) -> None:
    """min must be strictly less than max on both axes."""
    response = api_client.post(
        "/predict/bbox",
        json={"min_lon": 80.5, "min_lat": 21.9, "max_lon": 80.1, "max_lat": 21.5},
    )
    assert response.status_code == 422


def test_grid_points_respects_cap() -> None:
    """A tight grid over a wide bbox is coarsened rather than exceeding the cap."""
    from src.models.prospectivity.predict import grid_points

    points, step = grid_points(79.0, 21.3, 80.6, 22.1, grid_resolution_m=10, cap=500)

    assert len(points) <= 500
    assert step > 10.0  # widened to fit the cap

    # The grid covers the whole bbox and may overshoot the far edge by up to
    # one step, since each axis is inclusive of its end.
    margin = 0.1
    assert points.lon.between(79.0 - margin, 80.6 + margin).all()
    assert points.lat.between(21.3 - margin, 22.1 + margin).all()
    assert points.lon.max() >= 80.6 - margin  # eastern edge not truncated
    assert points.lat.max() >= 22.1 - margin  # northern edge not truncated


def test_v6_promotion_ordering() -> None:
    """Pin the first property that motivated promoting v1 -> v6.

    v1 scored MOIL's flagship mines near zero while scoring 0.990 at points
    whose features were entirely null - a near-inverted map. This half checks
    the flagship mines; test_v6_scores_null_feature_points_low checks the other.
    """
    from pathlib import Path

    import pytest as _pytest

    from src.models.prospectivity.predict import SHIPPED_MODEL_PATH, predict_point

    if not SHIPPED_MODEL_PATH.exists():
        _pytest.skip(f"{SHIPPED_MODEL_PATH.name} not present")
    assert SHIPPED_MODEL_PATH.name == "prospectivity_v6.pkl"

    # Flagship producing mines must score high.
    for lat, lon, name in ((21.8167, 80.1833, "Balaghat"), (21.4667, 79.6333, "Dongri Buzurg")):
        result = predict_point(lat, lon, model_path=Path(SHIPPED_MODEL_PATH), explain=False)
        assert result is not None, f"{name} unexpectedly outside the footprint"
        assert result["prospectivity_score"] > 0.5, f"{name} scored {result['prospectivity_score']}"


def test_v6_scores_null_feature_points_low() -> None:
    """The other half of the v1 -> v6 promotion: all-null features must score low.

    Kandri and Beldongri lie outside the Sausar mosaic, so they only reach the
    model through the national tiles in data/raw/satellite/unlabelled/. Without
    those rasters predict_point correctly returns None (no footprint, no score),
    and there is nothing to assert about the score.
    """
    from pathlib import Path

    from src.config.settings import settings
    from src.models.prospectivity.predict import SHIPPED_MODEL_PATH, predict_point

    if not SHIPPED_MODEL_PATH.exists():
        pytest.skip(f"{SHIPPED_MODEL_PATH.name} not present")
    if not any((settings.DATA_RAW / "satellite" / "unlabelled").glob("*.tif")):
        pytest.skip("national unlabelled tiles not present in data/raw/satellite/unlabelled/")

    for lat, lon, name in ((21.2667, 79.0, "Kandri"), (21.2833, 79.05, "Beldongri")):
        result = predict_point(lat, lon, model_path=Path(SHIPPED_MODEL_PATH), explain=False)
        assert result is not None, f"{name} unexpectedly outside every tile footprint"
        nulls = sum(1 for v in result["features_extracted"].values() if v is None)
        assert nulls == len(result["features_extracted"]), f"{name} expected all-null features"
        assert result["prospectivity_score"] < 0.1, (
            f"{name} scored {result['prospectivity_score']} on null features"
        )


def test_heatmap_grid_is_a_lattice_with_nulls_for_no_data() -> None:
    """The grid reshapes cleanly and marks no-data cells as None, not 0.0."""
    from src.models.prospectivity.predict import heatmap_grid

    grid = heatmap_grid(79.53, 21.32, 80.57, 22.05, grid_size=8)
    assert grid["grid"]["n_rows"] == 8 and grid["grid"]["n_cols"] == 8
    assert len(grid["scores"]) == 8 and all(len(row) == 8 for row in grid["scores"])
    assert grid["grid"]["origin"] == "top_left"
    cells = grid["cells"]
    assert cells["cells_total"] == 64
    assert cells["cells_scored"] + cells["cells_outside_raster"] == cells["cells_total"]
    for row in grid["scores"]:
        for value in row:
            assert value is None or 0.0 <= value <= grid["score_range"]["cap"]


def test_heatmap_grid_returns_nulls_outside_the_footprint() -> None:
    """A viewport straddling the raster edge yields null cells, not a crash.

    Gumgaon (21.2333, 78.9333) sits outside the imagery footprint; the heatmap
    loop calls the scoring path directly with no router to absorb a failure,
    so the no-data case has to be handled in the function itself.
    """
    from src.models.prospectivity.predict import heatmap_grid

    grid = heatmap_grid(78.85, 21.15, 79.30, 21.45, grid_size=8)
    flat = [v for row in grid["scores"] for v in row]
    assert len(flat) == 64
    assert any(v is None for v in flat), "expected no-data cells south of the DEM edge"
    assert grid["cells"]["cells_outside_raster"] > 0
