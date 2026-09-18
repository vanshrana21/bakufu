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


# --- horizon-adaptive routing -------------------------------------------


def test_route_model_sends_short_horizons_to_seasonal_naive() -> None:
    from src.api.routers.forecast import (
        REASON_NAIVE,
        REASON_PROPHET,
        SEASONAL_NAIVE_MAX_HORIZON,
        route_model,
    )

    assert SEASONAL_NAIVE_MAX_HORIZON == 6
    for horizon in (1, 3, 6):
        assert route_model(horizon) == ("seasonal_naive", REASON_NAIVE)
    assert route_model(12) == ("prophet", REASON_PROPHET)
    assert REASON_NAIVE == "seasonal_naive_beats_prophet_at_short_horizon"


def test_routing_is_justified_by_the_shipped_backtest() -> None:
    """Each horizon goes to whichever model had the lower backtest MAPE.

    If a re-promoted model shifts the balance, this fails instead of letting
    the API keep serving the worse forecast.
    """
    from src.api.routers.forecast import route_model, seasonal_naive_backtest
    from src.api.state import SHIPPED_BACKTEST_ROWS, SHIPPED_FORECAST_METRICS

    if not SHIPPED_BACKTEST_ROWS.exists() or not SHIPPED_FORECAST_METRICS.exists():
        pytest.skip("shipped backtest artifacts not present")

    rows = pd.read_parquet(SHIPPED_BACKTEST_ROWS)
    metrics = pd.read_json(SHIPPED_FORECAST_METRICS).set_index("horizon_months")
    for horizon in (1, 3, 6, 12):
        naive = seasonal_naive_backtest(rows, horizon)
        prophet_mape = float(metrics.loc[horizon, "mape"])
        # The recomputed naive accuracy must match the artifact it is compared to.
        assert naive["mape"] == pytest.approx(float(metrics.loc[horizon, "naive_mape"]))
        winner = "seasonal_naive" if naive["mape"] < prophet_mape else "prophet"
        assert route_model(horizon)[0] == winner, f"horizon {horizon}"


def test_seasonal_naive_backtest_measures_coverage_out_of_sample() -> None:
    """In-sample coverage of the 10-90 quantiles is ~80% by construction."""
    from src.api.routers.forecast import seasonal_naive_backtest

    ratios = np.linspace(0.8, 1.2, 21)
    rows = pd.DataFrame(
        {"horizon_months": 1, "naive": 100_000.0, "actual": 100_000.0 * ratios}
    )
    result = seasonal_naive_backtest(rows, 1)

    assert result["n_origins"] == 21
    assert result["ratio_lower"] == pytest.approx(np.quantile(ratios, 0.10))
    assert result["ratio_upper"] == pytest.approx(np.quantile(ratios, 0.90))
    assert result["mape"] == pytest.approx(np.mean(np.abs(ratios - 1) / ratios) * 100)

    lower, upper = np.quantile(ratios, [0.10, 0.90])
    in_sample = 100 * np.mean((ratios >= lower) & (ratios <= upper))
    assert result["ci80_coverage"] < in_sample
    assert seasonal_naive_backtest(rows, 12) is None, "no origins at that horizon"


def _synthetic_series(drop: str | None = None) -> pd.DataFrame:
    months = pd.period_range("2024-01", "2025-05", freq="M")
    frame = pd.DataFrame(
        {
            "report_month": months,
            "mh_plus_mp_qty_tonnes": 100_000.0 + np.arange(len(months)) * 1_000.0,
        }
    )
    if drop is not None:
        frame = frame[frame.report_month != pd.Period(drop, freq="M")]
    return frame


def test_seasonal_naive_forecast_uses_same_month_last_year() -> None:
    from src.api.routers.forecast import _seasonal_naive_forecast

    backtest = {"ratio_lower": 0.9, "ratio_upper": 1.2}
    out = _seasonal_naive_forecast(_synthetic_series(), 3, backtest)

    assert out["target_period"] == "2025-08"
    base = 100_000.0 + 7 * 1_000.0  # 2024-08 is the eighth month
    assert out["predicted_tonnes"] == pytest.approx(base)
    assert out["predicted_lower_ci"] == pytest.approx(base * 0.9)
    assert out["predicted_upper_ci"] == pytest.approx(base * 1.2)
    assert out["model"]["trained_through"] == "2025-05"


def test_seasonal_naive_series_reads_each_month_from_its_own_base() -> None:
    """Every month of the horizon comes from that month a year earlier."""
    from src.api.routers.forecast import _seasonal_naive_forecast

    backtest = {"ratio_lower": 0.9, "ratio_upper": 1.2}
    out = _seasonal_naive_forecast(_synthetic_series(), 3, backtest)
    series = out["series"]

    assert [point["month"] for point in series] == ["2025-06", "2025-07", "2025-08"]
    # The synthetic series climbs 1,000 t a month from 100,000 at 2024-01.
    assert [point["p50"] for point in series] == [105_000.0, 106_000.0, 107_000.0]
    assert series[-1]["p50"] == pytest.approx(out["predicted_tonnes"])


def test_seasonal_naive_series_is_dropped_when_an_intermediate_base_is_missing() -> None:
    """A hole inside the horizon must not reach the chart as a gap.

    The terminal point is still served: only the month-by-month series needs
    every base month present.
    """
    from src.api.routers.forecast import _seasonal_naive_forecast

    backtest = {"ratio_lower": 0.9, "ratio_upper": 1.2}
    out = _seasonal_naive_forecast(_synthetic_series(drop="2024-07"), 3, backtest)

    assert out is not None and out["predicted_tonnes"] > 0
    assert out["series"] == []


def test_seasonal_naive_declines_when_last_years_month_is_a_gap() -> None:
    """The series has gaps (2016-03, 2023-03); the router falls back to Prophet."""
    from src.api.routers.forecast import _seasonal_naive_forecast

    backtest = {"ratio_lower": 0.9, "ratio_upper": 1.2}
    assert _seasonal_naive_forecast(_synthetic_series(drop="2024-08"), 3, backtest) is None


def test_forecast_endpoint_routes_by_horizon() -> None:
    from fastapi.testclient import TestClient

    from src.api.main import app
    from src.api.state import PRODUCTION_SERIES

    if not PRODUCTION_SERIES.exists():
        pytest.skip("production series not present")

    series = pd.read_parquet(PRODUCTION_SERIES)
    tonnes = pd.Series(
        series.mh_plus_mp_qty_tonnes.to_numpy(dtype="float64"),
        index=pd.PeriodIndex(series.report_month, freq="M"),
    )

    with TestClient(app) as client:
        for horizon in (1, 3, 6):
            body = client.get("/forecast", params={"horizon": horizon}).json()
            assert body["model_used"] == "seasonal_naive"
            assert body["reason"] == "seasonal_naive_beats_prophet_at_short_horizon"
            last_year = pd.Period(body["target_period"], freq="M") - 12
            assert body["predicted_tonnes"] == pytest.approx(float(tonnes.loc[last_year]))
            assert body["predicted_lower_ci"] < body["predicted_tonnes"] < body["predicted_upper_ci"]

        body = client.get("/forecast", params={"horizon": 12}).json()
        assert body["model_used"] == "prophet"
        assert body["reason"] == "prophet_beats_seasonal_naive_at_long_horizon"
        assert "trend" in body["components"]
