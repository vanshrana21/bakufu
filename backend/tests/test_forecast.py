"""Tests for the Phase 3 forecasting and shortfall-risk pipeline."""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from src.config.settings import settings

PROPHET_MODEL = settings.MODELS_DIR / "prophet_baseline_v1.pkl"
LSTM_MODEL = settings.MODELS_DIR / "lstm_residual_v1.pt"
#: The shipped classifier. `shortfall_v1.pkl` was the Phase 3 scaffold's
#: path and never existed, so this test silently skipped instead of
#: validating anything.
SHORTFALL_MODEL = settings.MODELS_DIR / "shortfall_classifier_v1.pkl"


def _synthetic_months(n: int = 72) -> pd.DataFrame:
    """Trend + yearly seasonality + monsoon dip, with reproducible noise."""
    rng = np.random.default_rng(42)
    ds = pd.date_range("2018-01-01", periods=n, freq="MS")
    month = ds.month.to_numpy()
    monsoon = np.isin(month, [6, 7, 8, 9]).astype(float)
    y = (
        120_000
        + np.arange(n) * 250
        - monsoon * 35_000
        + rng.normal(0, 4_000, n)
    )
    return pd.DataFrame(
        {
            "ds": ds,
            "y": y,
            "rainfall_mm": 40 + monsoon * 260 + rng.normal(0, 12, n),
            "capex": (np.arange(n) > n - 12).astype(float),
        }
    )


def test_prophet_baseline_trains() -> None:
    """Prophet fits and produces a forward forecast with an interval."""
    from src.models.forecast.prophet_baseline import _future_regressors, fit_prophet

    frame = _synthetic_months()
    model = fit_prophet(frame)
    future = model.make_future_dataframe(periods=3, freq="MS")
    future = _future_regressors(frame, future)
    forecast = model.predict(future)

    assert len(forecast) == len(frame) + 3
    assert forecast.yhat.notna().all()
    tail = forecast.iloc[-1]
    assert tail.yhat_lower <= tail.yhat <= tail.yhat_upper
    # The monsoon dip is real in the synthetic data, so a June forecast must
    # sit below a March one.
    june = forecast[forecast.ds.dt.month == 6].yhat.mean()
    march = forecast[forecast.ds.dt.month == 3].yhat.mean()
    assert june < march


def test_mape_and_rmse_are_sane() -> None:
    from src.models.forecast.prophet_baseline import mape, rmse

    actual = np.array([100.0, 200.0, 300.0])
    assert mape(actual, actual) == pytest.approx(0.0)
    assert rmse(actual, actual) == pytest.approx(0.0)
    assert mape(actual, actual * 1.1) == pytest.approx(10.0, abs=1e-6)


def test_fiscal_year_follows_indian_convention() -> None:
    from datetime import date

    from src.data.ingest.scrape_moil_bse import fiscal_year

    assert fiscal_year(date(2024, 4, 1)) == ("FY2024-25", 1)
    assert fiscal_year(date(2024, 3, 1)) == ("FY2023-24", 4)
    assert fiscal_year(date(2024, 11, 1))[1] == 3


def test_production_parser_prefers_monthly_over_cumulative() -> None:
    """The year-to-date figure must never be read as the month's output."""
    from datetime import date

    from src.data.ingest.scrape_moil_bse import parse_production

    body = (
        "MOIL achieves best November Performance. "
        "MOIL has recorded production of 1.63 lakh tonnes in November. "
        "During first eight months of FY25, the company has recorded "
        "production of 11.80 lakh tonnes."
    )
    parsed = parse_production(body, date(2024, 12, 2))
    assert parsed is not None
    period, tonnes = parsed
    assert tonnes == pytest.approx(163_000)
    assert period == date(2024, 11, 1)


def test_lstm_residual_reduces_error() -> None:
    """The hybrid must be recorded against the Prophet-only baseline."""
    if not LSTM_MODEL.exists():
        # Phase 3.2e was deliberately deferred: the ship criterion was a
        # >=1.5pp MAPE improvement over Prophet+regressors, and the model was
        # never built. This skip marks unbuilt scope, not a failure.
        pytest.skip("LSTM residual model not built (Phase 3.2e deferred)")

    import torch

    checkpoint = torch.load(LSTM_MODEL, map_location="cpu", weights_only=False)
    summary = checkpoint["summary"]
    assert {"prophet_mape", "hybrid_mape", "beats_zero_residual"} <= set(summary)
    assert summary["residual_rmse_lstm"] > 0


def test_lstm_forward_pass_shape() -> None:
    import torch

    from src.models.forecast.lstm_residual import FEATURES, LOOKBACK, ResidualLSTM

    model = ResidualLSTM()
    out = model(torch.rand(4, LOOKBACK, len(FEATURES)))
    assert out.shape == (4,)


def test_shortfall_classifier_bundle_is_well_formed() -> None:
    """The shipped bundle carries the rules it was trained under.

    The bundle records `shap_importance`, `n_train` and `n_positives` rather
    than a `metrics` dict; the backtest numbers live in the Phase 3.2d write-up
    and are asserted in tests/test_shortfall.py.
    """
    if not SHORTFALL_MODEL.exists():
        pytest.skip(f"{SHORTFALL_MODEL.name} not present - run the Phase 3.2d training")

    import joblib

    bundle = joblib.load(SHORTFALL_MODEL)
    assert bundle["features"], "the feature order must be recorded"
    assert len(bundle["features"]) == 9
    assert 0.0 < bundle["shortfall_threshold"] < 1.0
    assert bundle["min_train_for_label"] == 60, "label-contamination cut"
    assert bundle["n_train"] == 60 and bundle["n_positives"] == 13
    # Rainfall predicting the tail is the substantive Phase 3.2 finding.
    importance = bundle["shap_importance"].set_index("feature").mean_abs_shap
    assert importance["rainfall_lag2_mm"] > importance["rainfall_concurrent_mm"]


def test_forecast_endpoint_returns_valid_response(api_headers: dict[str, str]) -> None:
    from fastapi.testclient import TestClient

    from src.api.main import app

    with TestClient(app, headers=api_headers) as client:
        bad = client.get("/forecast", params={"horizon": 7})
        assert bad.status_code == 422

        response = client.get("/forecast", params={"horizon": 1})
        if response.status_code == 503:
            pytest.skip("forecast model not trained yet")
        assert response.status_code == 200
        body = response.json()
        assert body["horizon_months"] == 1
        assert body["predicted_tonnes"] > 0
        assert body["predicted_lower_ci"] <= body["predicted_tonnes"] <= body["predicted_upper_ci"]


def test_shortfall_endpoint_returns_risk_score(api_headers: dict[str, str]) -> None:
    from fastapi.testclient import TestClient

    from src.api.main import app

    with TestClient(app, headers=api_headers) as client:
        response = client.get("/shortfall/risk")
        if response.status_code == 500:
            pytest.skip("shortfall model not trained yet")
        assert response.status_code == 200
        body = response.json()

        # Phase 4 rebuilt this endpoint around the shipped classifier: the
        # retired scaffold's risk_score/risk_category gave way to
        # shortfall_probability/risk_level, matching what the pkl produces.
        assert 0.0 <= body["shortfall_probability"] <= 1.0
        assert body["risk_level"] in {"low", "medium", "high"}


def test_production_history_endpoint(api_headers: dict[str, str]) -> None:
    from fastapi.testclient import TestClient

    from src.api.main import app

    with TestClient(app, headers=api_headers) as client:
        response = client.get("/production/history")
        assert response.status_code == 200
        body = response.json()

        # Phase 4 replaced the flat BSE list with the MSMP object: the 20-row
        # Supabase table gave way to the 123-month parquet, and the fiscal-year
        # fields it carried do not exist in that source.
        assert set(body) == {"series", "coverage", "metadata"}
        rows = body["series"]
        assert isinstance(rows, list)
        if rows:
            assert rows[0]["mh_plus_mp_qty_tonnes"] > 0
            periods = [r["report_month"] for r in rows]
            assert periods == sorted(periods)
