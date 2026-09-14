"""Integration tests for the Phase 4 dashboard endpoints.

Each endpoint is checked against `docs/phase_4/api_contracts.md`: response
shape, happy path, 422 on bad input, 500 with a machine-readable code when an
artifact is missing, and idempotency. The contract is what the frontend builds
against, so a divergence here is a real defect rather than a stale assertion.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.api.main import app
from src.api.state import Artifact, load_all


@pytest.fixture(scope="module")
def client() -> TestClient:
    # The context manager runs the lifespan handler, so artifacts are loaded.
    with TestClient(app) as test_client:
        yield test_client


# --- lifespan -----------------------------------------------------------


def test_lifespan_loads_every_served_artifact(client: TestClient) -> None:
    """Startup loads eagerly; a missing artifact must not crash the API."""
    state = app.state.artifacts
    expected = {
        "forecast_model", "forecast_metrics", "backtest_rows",
        "shortfall_model", "production_series", "shortfall_features",
    }
    assert expected <= set(state.artifacts)
    assert client.get("/").status_code == 200, "health must work regardless"


def test_shipped_artifacts_are_the_promoted_ones() -> None:
    """Endpoints must read promoted files, never the training scratch path.

    A training run once overwrote the served forecast model and the API
    silently served a rejected variant while returning 200.
    """
    from src.api import state as state_module

    assert state_module.SHIPPED_FORECAST_MODEL.name == "prophet_baseline_v1_0_shipped.pkl"
    assert "v1_0" in state_module.SHIPPED_FORECAST_METRICS.name
    assert state_module.SHIPPED_SHORTFALL_MODEL.name == "shortfall_classifier_v1.pkl"


def test_cors_allows_the_three_local_dev_origins() -> None:
    from src.api.main import ALLOWED_ORIGINS

    for port in (3000, 5173, 8080):
        assert f"http://localhost:{port}" in ALLOWED_ORIGINS


def test_requests_are_logged_with_elapsed_time(client: TestClient) -> None:
    response = client.get("/")
    assert "X-Elapsed-Ms" in response.headers
    assert float(response.headers["X-Elapsed-Ms"]) >= 0.0


# --- 1. GET /production/history ----------------------------------------


def test_production_history_shape_matches_contract(client: TestClient) -> None:
    body = client.get("/production/history").json()
    assert set(body) == {"series", "coverage", "metadata"}
    assert set(body["coverage"]) == {
        "months_present", "months_missing", "date_range", "gaps"
    }
    assert set(body["metadata"]) == {"source", "proxy_note"}
    row = body["series"][0]
    assert set(row) == {
        "report_month", "mh_qty_tonnes", "mp_qty_tonnes",
        "mh_plus_mp_qty_tonnes", "all_india_qty_tonnes", "extraction_method",
    }
    assert row["extraction_method"] in {"text", "ocr"}


def test_production_history_serves_the_msmp_series(client: TestClient) -> None:
    """123 months from the parquet, not the 20-row BSE table in Supabase."""
    body = client.get("/production/history").json()
    assert body["coverage"]["months_present"] == 123
    assert body["coverage"]["gaps"] == ["2016-03", "2023-03"]
    assert body["coverage"]["date_range"] == {"start": "2016-01", "end": "2026-05"}
    ocr = [r["report_month"] for r in body["series"] if r["extraction_method"] == "ocr"]
    assert ocr == ["2020-07", "2024-09", "2025-02", "2025-05", "2025-10"]


def test_production_history_coverage_is_window_scoped(client: TestClient) -> None:
    body = client.get("/production/history?start=2024-01&end=2026-05").json()
    assert body["coverage"]["months_present"] == 29
    assert body["coverage"]["gaps"] == []
    assert body["coverage"]["date_range"] == {"start": "2024-01", "end": "2026-05"}


@pytest.mark.parametrize(
    "query",
    ["?start=2024-13", "?start=notamonth", "?end=oops", "?start=2026-05&end=2024-01"],
)
def test_production_history_rejects_bad_params(client: TestClient, query: str) -> None:
    response = client.get(f"/production/history{query}")
    assert response.status_code == 422
    assert "detail" in response.json()


def test_production_history_empty_window_is_200(client: TestClient) -> None:
    """An empty result is a valid state, not an error."""
    response = client.get("/production/history?start=2030-01&end=2030-12")
    assert response.status_code == 200
    body = response.json()
    assert body["series"] == []
    assert body["coverage"]["months_present"] == 0


def test_production_history_is_idempotent(client: TestClient) -> None:
    first = client.get("/production/history?start=2024-01").json()
    second = client.get("/production/history?start=2024-01").json()
    assert first == second


def test_production_history_500s_when_the_series_is_missing(client: TestClient) -> None:
    """A missing artifact returns the documented flat error body."""
    from pathlib import Path

    state = app.state.artifacts
    saved = state.artifacts["production_series"]
    state.artifacts["production_series"] = Artifact(
        name="production_series",
        path=Path("msmp_mn_monthly_wide.parquet"),
        error="FileNotFoundError: gone",
    )
    try:
        response = client.get("/production/history")
        assert response.status_code == 500
        body = response.json()
        assert body["error_code"] == "model_not_loaded"
        assert "msmp_mn_monthly_wide.parquet" in body["detail"]
        assert "remedy" in body
    finally:
        state.artifacts["production_series"] = saved


# --- 2. GET /mines ------------------------------------------------------


def test_mines_shape_matches_contract(client: TestClient) -> None:
    body = client.get("/mines").json()
    assert set(body) == {"mines", "counts"}
    assert len(body["mines"]) == 10
    mine = body["mines"][0]
    assert set(mine) == {
        "mine_name", "state", "district", "mine_type", "equipment",
        "capacity_target_tonnes", "notes", "sources", "type_note",
    }
    assert all(set(s) == {"tag", "url"} for s in mine["sources"])


def test_mines_counts_match_the_reference_data(client: TestClient) -> None:
    """with_generic_fleet_only is 4, not 3 - Dongri Buzurg is included."""
    counts = client.get("/mines").json()["counts"]
    assert counts == {
        "total": 10, "underground": 7, "opencast": 3, "mixed": 0,
        "MH": 6, "MP": 4,
        "with_capacity_target": 3,
        "with_generic_fleet_only": 4,
    }


def test_mines_filters(client: TestClient) -> None:
    assert client.get("/mines?state=MP").json()["counts"]["total"] == 4
    assert client.get("/mines?state=MH").json()["counts"]["total"] == 6
    assert client.get("/mines?mine_type=underground").json()["counts"]["total"] == 7
    assert client.get("/mines?mine_type=opencast").json()["counts"]["total"] == 3


@pytest.mark.parametrize("query", ["?state=XX", "?mine_type=strip", "?state=maharashtra"])
def test_mines_rejects_bad_filters(client: TestClient, query: str) -> None:
    assert client.get(f"/mines{query}").status_code == 422


def test_mines_is_idempotent(client: TestClient) -> None:
    assert client.get("/mines").json() == client.get("/mines").json()


# --- 3. GET /mines/{mine_name} -----------------------------------------


def test_mine_detail_adds_fleet_vocabulary(client: TestClient) -> None:
    body = client.get("/mines/Kandri").json()
    assert body["mine_name"] == "Kandri"
    assert body["type_note"] and "mixed" in body["type_note"].lower()
    vocabulary = body["fleet_vocabulary"]
    assert set(vocabulary) == {"applicable", "is_generic_fallback"}
    assert vocabulary["is_generic_fallback"] is False
    assert "SDL" in vocabulary["applicable"]


@pytest.mark.parametrize(
    "name", ["Munsar", "Beldongri", "Sitapatore", "Dongri Buzurg"]
)
def test_generic_fleet_mines_are_flagged(client: TestClient, name: str) -> None:
    """All four placeholder-fleet mines report the fallback flag."""
    body = client.get(f"/mines/{name}").json()
    assert body["fleet_vocabulary"]["is_generic_fallback"] is True


def test_mine_detail_vocabulary_follows_mine_type(client: TestClient) -> None:
    opencast = client.get("/mines/Tirodi").json()["fleet_vocabulary"]["applicable"]
    underground = client.get("/mines/Balaghat").json()["fleet_vocabulary"]["applicable"]
    assert "drill_100mm" in opencast
    assert "SDL" in underground
    assert set(opencast) != set(underground)


def test_mine_detail_type_note_is_always_present(client: TestClient) -> None:
    """Emitted as null off Kandri, so the frontend need not probe for the key."""
    body = client.get("/mines/Balaghat").json()
    assert "type_note" in body and body["type_note"] is None


def test_unknown_mine_returns_404_listing_known_names(client: TestClient) -> None:
    response = client.get("/mines/Foo")
    assert response.status_code == 404
    detail = response.json()["detail"]
    assert "Foo" in detail and "Balaghat" in detail


def test_mine_name_with_a_space_resolves(client: TestClient) -> None:
    assert client.get("/mines/Dongri%20Buzurg").status_code == 200


def test_mine_detail_is_idempotent(client: TestClient) -> None:
    assert client.get("/mines/Ukwa").json() == client.get("/mines/Ukwa").json()


# --- 10. GET /prospectivity/heatmap ------------------------------------

WARM_BBOX = "min_lon=79.53&min_lat=21.32&max_lon=80.57&max_lat=22.05"


def test_heatmap_shape_matches_contract(client: TestClient) -> None:
    body = client.get(f"/prospectivity/heatmap?{WARM_BBOX}&grid_size=8").json()
    assert set(body) == {
        "bbox", "grid", "scores", "cells", "score_range",
        "mask_applied", "model_version", "generated_at", "cached",
    }
    assert set(body["grid"]) == {
        "n_cols", "n_rows", "cell_width_deg", "cell_height_deg", "origin"
    }
    assert set(body["cells"]) == {
        "cells_total", "cells_outside_raster", "cells_masked_out", "cells_scored"
    }
    assert set(body["score_range"]) == {"min", "max", "cap"}


def test_heatmap_is_a_lattice_aligned_to_the_bbox(client: TestClient) -> None:
    """Unlike /predict/bbox, every cell lies on a grid inside the request."""
    body = client.get(f"/prospectivity/heatmap?{WARM_BBOX}&grid_size=16").json()
    assert body["grid"]["n_rows"] == 16 and body["grid"]["n_cols"] == 16
    assert len(body["scores"]) == 16
    assert all(len(row) == 16 for row in body["scores"])
    assert body["grid"]["origin"] == "top_left"
    assert body["bbox"] == [79.53, 21.32, 80.57, 22.05]


def test_heatmap_scores_never_exceed_the_cap(client: TestClient) -> None:
    """float32 clipping can leave values a hair above 0.99; the legend reads
    ">= 0.99", so the contract's ceiling has to actually hold."""
    body = client.get(f"/prospectivity/heatmap?{WARM_BBOX}&grid_size=16").json()
    cap = body["score_range"]["cap"]
    for row in body["scores"]:
        for value in row:
            assert value is None or 0.0 <= value <= cap
    assert body["score_range"]["max"] <= cap


def test_heatmap_cell_accounting_adds_up(client: TestClient) -> None:
    cells = client.get(f"/prospectivity/heatmap?{WARM_BBOX}&grid_size=8").json()["cells"]
    assert cells["cells_total"] == 64
    assert cells["cells_scored"] + cells["cells_outside_raster"] == cells["cells_total"]


def test_heatmap_returns_nulls_outside_the_footprint(client: TestClient) -> None:
    """Gumgaon's latitude has no DEM, so those cells are no-data, not zero."""
    body = client.get(
        "/prospectivity/heatmap?min_lon=78.85&min_lat=21.15&max_lon=79.30&max_lat=21.45&grid_size=8"
    ).json()
    flat = [v for row in body["scores"] for v in row]
    assert any(v is None for v in flat)
    assert body["cells"]["cells_outside_raster"] == sum(1 for v in flat if v is None)


def test_heatmap_serves_the_promoted_model(client: TestClient) -> None:
    body = client.get(f"/prospectivity/heatmap?{WARM_BBOX}&grid_size=8").json()
    assert body["model_version"] == "prospectivity_v6"


@pytest.mark.parametrize(
    "query",
    [
        f"{WARM_BBOX}&grid_size=4",
        f"{WARM_BBOX}&grid_size=200",
        f"{WARM_BBOX}&mask=bogus",
        "min_lon=80&min_lat=21.3&max_lon=79&max_lat=22",
    ],
)
def test_heatmap_rejects_bad_params(client: TestClient, query: str) -> None:
    assert client.get(f"/prospectivity/heatmap?{query}").status_code == 422


def test_heatmap_mask_vocabulary_matches_predict_endpoints() -> None:
    """One mask vocabulary across every prospectivity endpoint."""
    from src.api.routers.predictions import VALID_MASKS as PREDICT_MASKS
    from src.data.masks.registry import VALID_MASKS

    assert tuple(PREDICT_MASKS) == tuple(VALID_MASKS)
    assert set(VALID_MASKS) == {"none", "geological", "occurrence_buffer", "both"}


def test_heatmap_is_cached_and_idempotent(client: TestClient) -> None:
    first = client.get(f"/prospectivity/heatmap?{WARM_BBOX}&grid_size=8").json()
    second = client.get(f"/prospectivity/heatmap?{WARM_BBOX}&grid_size=8").json()
    assert second["cached"] is True, "the second call must hit the cache"
    assert first["scores"] == second["scores"]


def test_heatmap_cache_key_includes_the_model_version() -> None:
    """A promotion must not be able to serve stale tiles."""
    from src.api.routers.reference import _cache_key

    bbox = (79.53, 21.32, 80.57, 22.05)
    assert _cache_key(bbox, 32, "none", "prospectivity_v1") != _cache_key(
        bbox, 32, "none", "prospectivity_v6"
    )


# --- 4. GET /forecast ---------------------------------------------------


def test_forecast_shape_matches_contract(client: TestClient) -> None:
    body = client.get("/forecast?horizon=1").json()
    assert set(body) == {
        "forecast_date", "target_period", "horizon_months", "predicted_tonnes",
        "predicted_lower_ci", "predicted_upper_ci", "ci_level", "components",
        "model", "accuracy_at_horizon",
    }
    assert set(body["model"]) == {
        "version", "variant", "regressors", "trained_through",
        "changepoint_prior_scale", "mcmc_samples",
    }
    assert set(body["accuracy_at_horizon"]) == {
        "mape", "naive_mape", "skill_vs_naive_pp", "ci80_coverage", "rmse", "n_origins"
    }


def test_forecast_reports_the_declared_model_version(client: TestClient) -> None:
    """The bundle carries no version string, so the API declares one."""
    from src.api.state import FORECAST_MODEL_VERSION

    body = client.get("/forecast?horizon=1").json()
    assert body["model"]["version"] == FORECAST_MODEL_VERSION == "prophet_baseline_v1.0"
    assert body["model"]["variant"] == "vanilla"
    assert body["model"]["regressors"] == [], "the shipped bundle has no regressors"


def test_forecast_components_are_whatever_the_model_has(client: TestClient) -> None:
    """Not a fixed set: a vanilla bundle has no rainfall or capex term."""
    components = client.get("/forecast?horizon=1").json()["components"]
    assert "trend" in components
    assert "rain_lag1" not in components and "capex" not in components
    assert all(isinstance(v, float) for v in components.values())


@pytest.mark.parametrize("horizon", [1, 3, 6, 12])
def test_forecast_accuracy_comes_from_the_shipped_backtest(
    client: TestClient, horizon: int
) -> None:
    """Metrics are read from the artifact, never recomputed live."""
    import pandas as pd

    from src.api.state import SHIPPED_FORECAST_METRICS

    metrics = pd.read_json(SHIPPED_FORECAST_METRICS)
    expected = metrics[metrics.horizon_months == horizon].iloc[0]
    accuracy = client.get(f"/forecast?horizon={horizon}").json()["accuracy_at_horizon"]
    assert accuracy["mape"] == pytest.approx(float(expected.mape))
    assert accuracy["skill_vs_naive_pp"] == pytest.approx(float(expected.skill_vs_naive_pp))
    assert accuracy["n_origins"] == int(expected.n_origins)


def test_forecast_target_period_advances_with_horizon(client: TestClient) -> None:
    one = client.get("/forecast?horizon=1").json()
    twelve = client.get("/forecast?horizon=12").json()
    assert one["target_period"] == "2026-06"
    assert twelve["target_period"] == "2027-05"
    assert one["ci_level"] == 0.80


def test_forecast_interval_brackets_the_point_estimate(client: TestClient) -> None:
    body = client.get("/forecast?horizon=1").json()
    assert body["predicted_lower_ci"] < body["predicted_tonnes"] < body["predicted_upper_ci"]


@pytest.mark.parametrize("horizon", [0, 2, 7, 24, -1])
def test_forecast_rejects_unbacktested_horizons(client: TestClient, horizon: int) -> None:
    assert client.get(f"/forecast?horizon={horizon}").status_code == 422


def test_forecast_is_idempotent(client: TestClient) -> None:
    first = client.get("/forecast?horizon=6").json()
    second = client.get("/forecast?horizon=6").json()
    assert first == second


def test_forecast_500s_when_the_model_is_missing(client: TestClient) -> None:
    from pathlib import Path

    from src.api.routers.forecast import clear_forecast_cache

    state = app.state.artifacts
    saved = state.artifacts["forecast_model"]
    clear_forecast_cache()  # otherwise the memoised payload masks the failure
    state.artifacts["forecast_model"] = Artifact(
        name="forecast_model",
        path=Path("prophet_baseline_v1_0_shipped.pkl"),
        error="FileNotFoundError: gone",
    )
    try:
        response = client.get("/forecast?horizon=1")
        assert response.status_code == 500
        assert response.json()["error_code"] == "model_not_loaded"
    finally:
        state.artifacts["forecast_model"] = saved
        clear_forecast_cache()


# --- 5. GET /forecast/history ------------------------------------------


def test_forecast_history_shape_matches_contract(client: TestClient) -> None:
    body = client.get("/forecast/history").json()
    assert set(body) == {"horizons", "origins", "model", "benchmark"}
    assert set(body["horizons"][0]) == {
        "horizon_months", "n_origins", "mape", "rmse",
        "naive_mape", "skill_vs_naive_pp", "ci80_coverage",
    }
    assert set(body["origins"][0]) == {
        "horizon_months", "origin_month", "target_month",
        "actual_tonnes", "predicted_tonnes", "covered",
    }
    assert body["benchmark"]["name"] == "seasonal_naive"


def test_forecast_history_covers_all_four_horizons(client: TestClient) -> None:
    body = client.get("/forecast/history").json()
    assert sorted(h["horizon_months"] for h in body["horizons"]) == [1, 3, 6, 12]
    assert len(body["origins"]) == 82, "82 origins across the four horizons"


def test_forecast_history_records_the_negative_short_horizon_skill(
    client: TestClient,
) -> None:
    """Honest framing is structural: the model loses to naive below 12 months."""
    horizons = {h["horizon_months"]: h for h in client.get("/forecast/history").json()["horizons"]}
    assert horizons[1]["skill_vs_naive_pp"] < 0
    assert horizons[12]["skill_vs_naive_pp"] > 0


def test_forecast_history_agrees_with_the_forecast_endpoint(client: TestClient) -> None:
    history = {h["horizon_months"]: h for h in client.get("/forecast/history").json()["horizons"]}
    for horizon in (1, 3, 6, 12):
        accuracy = client.get(f"/forecast?horizon={horizon}").json()["accuracy_at_horizon"]
        assert accuracy["mape"] == pytest.approx(history[horizon]["mape"])


def test_forecast_history_is_idempotent(client: TestClient) -> None:
    assert client.get("/forecast/history").json() == client.get("/forecast/history").json()


# --- 6. GET /shortfall/risk --------------------------------------------


def test_shortfall_shape_matches_contract(client: TestClient) -> None:
    body = client.get("/shortfall/risk").json()
    assert set(body) == {
        "as_of", "forecast_month", "shortfall_probability", "risk_level",
        "shortfall_definition", "prophet_forecast_tonnes",
        "shortfall_threshold_tonnes", "feature_contributions",
        "shap_base_value", "feature_provenance", "model_metadata",
    }
    assert set(body["feature_provenance"]) == {"rainfall", "prophet_forecast"}
    assert set(body["model_metadata"]) == {
        "version", "base_rate", "roc_auc", "pr_auc",
        "trained_on_months", "trained_on_positives", "decision_threshold",
    }


def test_shortfall_scores_the_next_unobserved_month(client: TestClient) -> None:
    """Not a re-score of the last historical month."""
    body = client.get("/shortfall/risk").json()
    assert body["as_of"] == "2026-05"
    assert body["forecast_month"] == "2026-06"


def test_shortfall_returns_all_nine_features_sorted(client: TestClient) -> None:
    """The API does not decide how many the UI shows."""
    contributions = client.get("/shortfall/risk").json()["feature_contributions"]
    assert len(contributions) == 9
    magnitudes = [abs(c["shap_contribution"]) for c in contributions]
    assert magnitudes == sorted(magnitudes, reverse=True)
    for entry in contributions:
        assert set(entry) == {
            "feature_name", "human_label", "value",
            "display_value", "shap_contribution", "direction",
        }
        assert entry["direction"] in {"increases_risk", "decreases_risk"}
        assert entry["human_label"] != entry["feature_name"], "must be human readable"


def test_shortfall_shap_reconciles_to_the_probability(client: TestClient) -> None:
    """base + sum(contributions), through a sigmoid, equals the probability.

    Without this the frontend's waterfall chart would not add up.
    """
    import math

    body = client.get("/shortfall/risk").json()
    total = body["shap_base_value"] + sum(
        c["shap_contribution"] for c in body["feature_contributions"]
    )
    assert 1.0 / (1.0 + math.exp(-total)) == pytest.approx(
        body["shortfall_probability"], abs=1e-6
    )


def test_shortfall_threshold_is_90_percent_of_the_forecast(client: TestClient) -> None:
    body = client.get("/shortfall/risk").json()
    assert body["shortfall_threshold_tonnes"] == pytest.approx(
        body["prophet_forecast_tonnes"] * 0.90
    )


def test_shortfall_risk_level_matches_the_probability(client: TestClient) -> None:
    body = client.get("/shortfall/risk").json()
    probability, level = body["shortfall_probability"], body["risk_level"]
    expected = "high" if probability >= 0.50 else "medium" if probability >= 0.25 else "low"
    assert level == expected


def test_shortfall_records_rainfall_provenance(client: TestClient) -> None:
    """A silent climatology fallback produced a false null in Phase 3.2c."""
    provenance = client.get("/shortfall/risk").json()["feature_provenance"]
    assert provenance["rainfall"] in {"observed", "imputed_climatology"}
    assert provenance["prophet_forecast"] == "shipped_model"


def test_shortfall_metadata_reports_the_small_training_set(client: TestClient) -> None:
    """Honest framing: 60 months, 13 positives, a screen not a prediction."""
    metadata = client.get("/shortfall/risk").json()["model_metadata"]
    assert metadata["version"] == "shortfall_classifier_v1"
    assert metadata["trained_on_months"] == 60
    assert metadata["trained_on_positives"] == 13
    assert metadata["roc_auc"] == pytest.approx(0.749)


def test_shortfall_is_idempotent(client: TestClient) -> None:
    assert client.get("/shortfall/risk").json() == client.get("/shortfall/risk").json()


def test_shortfall_500s_when_the_model_is_missing(client: TestClient) -> None:
    from pathlib import Path

    from src.api.routers.shortfall import clear_shortfall_cache

    state = app.state.artifacts
    saved = state.artifacts["shortfall_model"]
    clear_shortfall_cache()  # otherwise the memoised payload masks the failure
    state.artifacts["shortfall_model"] = Artifact(
        name="shortfall_model",
        path=Path("shortfall_classifier_v1.pkl"),
        error="FileNotFoundError: gone",
    )
    try:
        response = client.get("/shortfall/risk")
        assert response.status_code == 500
        assert response.json()["error_code"] == "model_not_loaded"
    finally:
        state.artifacts["shortfall_model"] = saved
        clear_shortfall_cache()


# --- route registry -----------------------------------------------------

EXPECTED_ROUTES = {
    ("GET", "/"),
    ("GET", "/boreholes"),
    ("GET", "/boreholes/{borehole_id}"),
    ("GET", "/boreholes/{borehole_id}/features"),
    ("GET", "/dashboard/summary"),
    ("GET", "/forecast"),
    ("GET", "/forecast/history"),
    ("POST", "/forecast/retrain"),
    ("GET", "/forecast/retrain/{task_id}"),
    ("GET", "/foreign"),
    ("GET", "/masks"),
    ("GET", "/mines"),
    ("GET", "/mines/{mine_name}"),
    ("POST", "/predict/bbox"),
    ("POST", "/predict/point"),
    ("GET", "/predictions/{prediction_id}"),
    ("GET", "/priors"),
    ("GET", "/priors/{block_name}"),
    ("GET", "/production/history"),
    ("GET", "/prospectivity/heatmap"),
    ("GET", "/recommendations"),
    ("GET", "/recommendations/scenario/{month}"),
    ("GET", "/shortfall/risk"),
    ("POST", "/train"),
    ("GET", "/train/{task_id}"),
}


def test_all_expected_routes_are_registered() -> None:
    """Guards against a refactor silently dropping an endpoint.

    Rewiring /forecast once cut /shortfall/risk out of the same file, and the
    endpoint 404'd until the suite caught it. This makes that failure loud.
    """
    spec = app.openapi()["paths"]
    registered = {
        (method.upper(), path)
        for path, operations in spec.items()
        for method in operations
    }
    missing = EXPECTED_ROUTES - registered
    unexpected = registered - EXPECTED_ROUTES
    assert not missing, f"routes disappeared: {sorted(missing)}"
    assert not unexpected, f"undocumented routes appeared: {sorted(unexpected)}"


# --- 7. GET /dashboard/summary -----------------------------------------


def test_dashboard_summary_shape_matches_contract(client: TestClient) -> None:
    body = client.get("/dashboard/summary").json()
    assert set(body) == {
        "generated_at", "latest_actual", "next_forecast", "shortfall",
        "series_health", "model_health", "mines", "degraded",
    }
    assert set(body["latest_actual"]) == {"month", "mh_plus_mp_tonnes", "all_india_tonnes"}
    assert set(body["next_forecast"]) == {
        "month", "predicted_tonnes", "lower_ci", "upper_ci", "ci_level"
    }
    assert set(body["shortfall"]) == {"month", "probability", "risk_level"}


def test_dashboard_summary_agrees_with_its_components(client: TestClient) -> None:
    """The aggregate must not drift from the endpoints it composes."""
    summary = client.get("/dashboard/summary").json()
    forecast = client.get("/forecast?horizon=1").json()
    risk = client.get("/shortfall/risk").json()

    assert summary["next_forecast"]["predicted_tonnes"] == pytest.approx(
        forecast["predicted_tonnes"]
    )
    assert summary["shortfall"]["probability"] == pytest.approx(
        risk["shortfall_probability"]
    )
    assert summary["shortfall"]["month"] == risk["forecast_month"]


def test_dashboard_summary_is_healthy_when_everything_loads(client: TestClient) -> None:
    body = client.get("/dashboard/summary").json()
    assert body["degraded"] == []
    assert body["series_health"]["months_present"] == 123
    assert body["series_health"]["ocr_recovered_months"] == 5
    assert body["model_health"]["best_horizon"]["horizon_months"] == 12


def test_dashboard_degrades_with_null_not_a_missing_key(client: TestClient) -> None:
    """A missing key and a null key behave differently in a TS client."""
    from pathlib import Path

    from src.api.routers.shortfall import clear_shortfall_cache

    state = app.state.artifacts
    saved = state.artifacts["shortfall_model"]
    clear_shortfall_cache()
    state.artifacts["shortfall_model"] = Artifact(
        name="shortfall_model",
        path=Path("shortfall_classifier_v1.pkl"),
        error="FileNotFoundError: gone",
    )
    try:
        response = client.get("/dashboard/summary")
        assert response.status_code == 200, "one dead component must not 500 the page"
        body = response.json()
        assert "shortfall" in body, "the key must still be present"
        assert body["shortfall"] is None
        assert "shortfall" in body["degraded"]
        # Everything else still renders.
        assert body["latest_actual"] is not None
        assert body["next_forecast"] is not None
    finally:
        state.artifacts["shortfall_model"] = saved
        clear_shortfall_cache()


def test_dashboard_summary_is_fast_once_warm(client: TestClient) -> None:
    """Composed latency is three cache reads, not three cold computations."""
    import time

    client.get("/dashboard/summary")  # ensure components are memoised
    started = time.perf_counter()
    client.get("/dashboard/summary")
    assert (time.perf_counter() - started) < 0.5


# --- 8. POST /forecast/retrain, GET /recommendations (501 stubs) --------


def test_retrain_is_stubbed_501(client: TestClient) -> None:
    response = client.post("/forecast/retrain")
    assert response.status_code == 501
    body = response.json()
    assert body["error_code"] == "not_implemented"
    assert "remedy" in body


def test_retrain_cannot_overwrite_the_shipped_model(client: TestClient) -> None:
    """The stub exists precisely because the old one wrote to the served path."""
    from src.api.state import SHIPPED_FORECAST_MODEL

    before = SHIPPED_FORECAST_MODEL.stat().st_mtime
    client.post("/forecast/retrain")
    assert SHIPPED_FORECAST_MODEL.stat().st_mtime == before


def test_recommendations_is_wired(client: TestClient) -> None:
    """Bucket 2 replaced the 501 stub with the rules engine."""
    response = client.get("/recommendations")
    assert response.status_code == 200
    assert "recommendations" in response.json()


@pytest.mark.parametrize("query", ["?mine_name=Foo", "?limit=0", "?limit=50"])
def test_recommendations_validates_before_stubbing(client: TestClient, query: str) -> None:
    """Params validate so the frontend can test error handling now."""
    assert client.get(f"/recommendations{query}").status_code == 422


def test_recommendations_accepts_a_known_mine(client: TestClient) -> None:
    assert client.get("/recommendations?mine_name=Balaghat&limit=3").status_code == 200


# --- shortfall disk cache ----------------------------------------------


def test_shortfall_cache_persists_to_disk(client: TestClient) -> None:
    """Survives a restart: a cold call is 6.6s and would hang the demo."""
    from src.api.routers.shortfall import _cache_path, clear_shortfall_cache

    body = client.get("/shortfall/risk").json()
    path = _cache_path(body["as_of"], body["forecast_month"])
    assert path.exists(), "the payload must be persisted"

    clear_shortfall_cache()  # simulate a process restart
    reloaded = client.get("/shortfall/risk").json()
    assert reloaded["shortfall_probability"] == body["shortfall_probability"]


def test_shortfall_cache_key_includes_both_months() -> None:
    """A new MSMP month must miss the cache rather than serve a stale score."""
    from src.api.routers.shortfall import _cache_path

    assert _cache_path("2026-05", "2026-06") != _cache_path("2026-06", "2026-07")
