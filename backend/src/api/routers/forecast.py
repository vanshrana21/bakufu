"""Production forecasting and shortfall-risk endpoints (Phase 3)."""

from __future__ import annotations

import traceback
import uuid
from datetime import UTC, date, datetime
from typing import Any

import numpy as np
import pandas as pd
from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Request

from src.api.schemas import (
    ShortfallRiskOut,
    TrainStatusOut,
    TrainTaskOut,
)

from src.api.errors import NotImplementedInDemo, PredictionFailed
from src.api.state import FORECAST_MODEL_VERSION
from src.models.forecast.prophet_baseline import CHANGEPOINT_PRIOR_SCALE, _future_regressors

router = APIRouter(tags=["forecast"])

VALID_HORIZONS: tuple[int, ...] = (1, 3, 6, 12)

#: Horizon-adaptive routing. Over the shipped backtest's rolling origins,
#: seasonal-naive (same calendar month one year earlier) beats Prophet at every
#: horizon up to six months - MAPE 9.67 / 10.05 / 10.71 against 10.93 / 11.74 /
#: 12.54 at horizons 1 / 3 / 6 - and Prophet wins only at 12 (9.92 against
#: 10.16). Serving Prophet at short horizons showed users the worse forecast.
#:
#: A trend-adjusted naive (base scaled by trailing 12-month or 3-month growth)
#: was backtested on the same origins and rejected: at horizon 1 it scores
#: 13.00 and 11.07 MAPE, worse than Prophet itself, so the served naive is the
#: plain one the benchmark actually measured.
SEASONAL_NAIVE_MAX_HORIZON = 6
SEASONAL_NAIVE_VERSION = "seasonal_naive_v1"

REASON_NAIVE = "seasonal_naive_beats_prophet_at_short_horizon"
REASON_PROPHET = "prophet_beats_seasonal_naive_at_long_horizon"
#: Fallback when the same-month-last-year actual is one of the series gaps.
REASON_NAIVE_UNAVAILABLE = "seasonal_naive_base_month_missing"

CI_LEVEL = 0.80
_CI_QUANTILES = (0.10, 0.90)

#: Prophet's MCMC posterior makes a predict() call ~950ms, over the 500ms
#: target. The bundle is immutable for the life of the process and there are
#: only four valid horizons, so the result is memoised rather than recomputed.
#: Cleared when the lifespan handler reloads artifacts.
_FORECAST_CACHE: dict[int, dict[str, Any]] = {}


def clear_forecast_cache() -> None:
    _FORECAST_CACHE.clear()

#: In-process registry of retrain jobs, mirroring the predictions router.
_FORECAST_TASKS: dict[str, dict[str, Any]] = {}


def _unavailable(exc: Exception, what: str) -> HTTPException:
    return HTTPException(
        status_code=503,
        detail=(
            f"{what} is unavailable: {exc}. Run the Phase 3 pipeline - "
            "python -m src.data.ingest.scrape_moil_bse, then "
            "python -m src.models.forecast.prophet_baseline"
        ),
    )


def route_model(horizon: int) -> tuple[str, str]:
    """Which model serves `horizon`, and the reason code the response reports."""
    if horizon <= SEASONAL_NAIVE_MAX_HORIZON:
        return "seasonal_naive", REASON_NAIVE
    return "prophet", REASON_PROPHET


def _mape(actual: np.ndarray, predicted: np.ndarray) -> float:
    return float(np.mean(np.abs(actual - predicted) / actual) * 100.0)


def _rmse(actual: np.ndarray, predicted: np.ndarray) -> float:
    return float(np.sqrt(np.mean((actual - predicted) ** 2)))


def seasonal_naive_backtest(rows: pd.DataFrame, horizon: int) -> dict[str, Any] | None:
    """Seasonal-naive accuracy and interval on the shipped backtest origins.

    Uses the same origins Prophet was scored on, so the two are compared like
    for like. The interval is empirical: the 10th and 90th percentiles of
    actual / naive at this horizon. Its coverage is measured leave-one-out,
    because in-sample coverage of those quantiles is ~80% by construction and
    would validate nothing.
    """
    at = rows[rows.horizon_months == horizon]
    if len(at) < 3:
        return None
    actual = at.actual.to_numpy(dtype="float64")
    naive = at.naive.to_numpy(dtype="float64")
    ratios = actual / naive
    lower, upper = (float(q) for q in np.quantile(ratios, _CI_QUANTILES))

    covered = []
    for index in range(len(ratios)):
        lo, hi = np.quantile(np.delete(ratios, index), _CI_QUANTILES)
        covered.append(lo <= ratios[index] <= hi)

    return {
        "mape": _mape(actual, naive),
        "rmse": _rmse(actual, naive),
        "ci80_coverage": float(np.mean(covered) * 100.0),
        "n_origins": int(len(at)),
        "ratio_lower": lower,
        "ratio_upper": upper,
    }


def _month_label(period: pd.Period) -> str:
    """"2026-06" -> "Jun 2026", the label the chart axis renders."""
    return period.strftime("%b %Y")


def _naive_interval_at(rows: pd.DataFrame, months_ahead: int) -> tuple[float, float]:
    """Interval ratios for a month `months_ahead` out.

    Only 1, 3, 6 and 12 are backtested, so an intermediate month borrows the
    nearest backtested horizon at or below it - month 2 uses the 1-month
    ratios, month 5 the 3-month ones. Borrowing downward is the conservative
    direction: a shorter horizon has the tighter interval, so this never
    widens an interval on evidence that does not exist.
    """
    candidates = [h for h in VALID_HORIZONS if h <= months_ahead] or [min(VALID_HORIZONS)]
    backtest = seasonal_naive_backtest(rows, max(candidates))
    if backtest is None:
        return 1.0, 1.0
    return backtest["ratio_lower"], backtest["ratio_upper"]


def _prophet_accuracy(metrics: pd.DataFrame, horizon: int) -> dict[str, Any] | None:
    """The shipped backtest row, read from the artifact rather than recomputed."""
    at = metrics[metrics.horizon_months == horizon]
    if not len(at):
        return None
    row = at.iloc[0]
    return {
        "mape": float(row.mape),
        "naive_mape": float(row.naive_mape),
        "skill_vs_naive_pp": float(row.skill_vs_naive_pp),
        "ci80_coverage": float(row.ci80_coverage),
        "rmse": float(row.rmse),
        "n_origins": int(row.n_origins),
    }


def _accuracy_at_horizon(
    model_used: str,
    prophet: dict[str, Any] | None,
    naive: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Accuracy of the model actually served, with the alternative alongside."""
    if prophet is None or naive is None:
        return None
    if model_used == "prophet":
        return {**prophet, "prophet_mape": prophet["mape"]}
    return {
        "mape": naive["mape"],
        "naive_mape": prophet["naive_mape"],
        "prophet_mape": prophet["mape"],
        "skill_vs_naive_pp": 0.0,
        "ci80_coverage": naive["ci80_coverage"],
        "rmse": naive["rmse"],
        "n_origins": naive["n_origins"],
    }


def _prophet_forecast(bundle: dict[str, Any], horizon: int) -> dict[str, Any]:
    model, frame = bundle["model"], bundle["frame"]
    try:
        future = model.make_future_dataframe(periods=horizon, freq="MS")
        future = _future_regressors(frame, future, as_of=frame.ds.iloc[-1], full=frame)
        forecast = model.predict(future)
    except Exception as exc:  # noqa: BLE001 - surfaced with a code
        raise PredictionFailed(f"prophet prediction failed: {exc}") from exc

    row = forecast.iloc[-1]
    # One point per month of the horizon. The fit already produces them; the
    # terminal row alone cannot be expanded back into the months in between.
    series = [
        {
            "month": pd.Period(entry.ds, freq="M").strftime("%Y-%m"),
            "month_label": _month_label(pd.Period(entry.ds, freq="M")),
            "p10": float(entry.yhat_lower),
            "p50": float(entry.yhat),
            "p90": float(entry.yhat_upper),
        }
        for entry in forecast.iloc[-horizon:].itertuples()
    ]

    # Whatever components this fitted model actually has - a vanilla bundle has
    # no rainfall or capex term, so the frontend iterates rather than indexing.
    components = {
        name: float(row[name])
        for name in ("trend", "yearly", "weekly", "daily",
                     "additive_terms", "multiplicative_terms",
                     "rain_lag1", "rain_lag2", "capex")
        if name in forecast.columns
    }

    return {
        "forecast_date": date.today().isoformat(),
        "target_period": pd.Period(row.ds, freq="M").strftime("%Y-%m"),
        "horizon_months": horizon,
        "predicted_tonnes": float(row.yhat),
        "predicted_lower_ci": float(row.yhat_lower),
        "predicted_upper_ci": float(row.yhat_upper),
        "ci_level": CI_LEVEL,
        "series": series,
        "components": components,
        "model": {
            "version": FORECAST_MODEL_VERSION,
            "variant": bundle.get("variant", "vanilla"),
            "regressors": list(bundle.get("regressors") or []),
            "trained_through": pd.Period(frame.ds.max(), freq="M").strftime("%Y-%m"),
            "changepoint_prior_scale": CHANGEPOINT_PRIOR_SCALE,
            "mcmc_samples": 300,
            "interval_method": "mcmc_posterior",
        },
    }


def _seasonal_naive_forecast(
    series: pd.DataFrame,
    horizon: int,
    backtest: dict[str, Any] | None,
    rows: pd.DataFrame | None = None,
) -> dict[str, Any] | None:
    """Same calendar month one year earlier. None when that month is a gap."""
    if backtest is None:
        return None
    months = pd.PeriodIndex(series.report_month, freq="M")
    tonnes = pd.Series(series.mh_plus_mp_qty_tonnes.to_numpy(dtype="float64"), index=months)
    last = months.max()
    target = last + horizon
    base_month = target - 12
    if base_month not in tonnes.index or pd.isna(tonnes.loc[base_month]):
        return None
    base = float(tonnes.loc[base_month])

    # One point per month of the horizon, each from its own base month. A month
    # whose base is a series gap stops the series: the chart must not carry a
    # hole, and the terminal point is still served on its own.
    points: list[dict[str, Any]] = []
    for step in range(1, horizon + 1):
        month = last + step
        source = month - 12
        if source not in tonnes.index or pd.isna(tonnes.loc[source]):
            points = []
            break
        value = float(tonnes.loc[source])
        lower, upper = (
            _naive_interval_at(rows, step)
            if rows is not None
            else (backtest["ratio_lower"], backtest["ratio_upper"])
        )
        points.append(
            {
                "month": month.strftime("%Y-%m"),
                "month_label": _month_label(month),
                "p10": value * lower,
                "p50": value,
                "p90": value * upper,
            }
        )

    return {
        "forecast_date": date.today().isoformat(),
        "target_period": target.strftime("%Y-%m"),
        "horizon_months": horizon,
        "predicted_tonnes": base,
        "predicted_lower_ci": base * backtest["ratio_lower"],
        "predicted_upper_ci": base * backtest["ratio_upper"],
        "ci_level": CI_LEVEL,
        "series": points,
        "components": {"same_month_last_year_tonnes": base},
        "model": {
            "version": SEASONAL_NAIVE_VERSION,
            "variant": "seasonal_naive",
            "regressors": [],
            "trained_through": last.strftime("%Y-%m"),
            "changepoint_prior_scale": None,
            "mcmc_samples": None,
            "interval_method": "empirical_backtest_ratio_quantiles",
        },
    }


@router.get("/forecast", summary="Forecast MH+MP production")
def get_forecast(request: Request, horizon: int = Query(1, description=f"Months ahead. One of {VALID_HORIZONS}.")) -> dict[str, Any]:
    """Forecast at one of the backtested horizons, from whichever model wins there.

    Horizons up to `SEASONAL_NAIVE_MAX_HORIZON` are served by seasonal-naive,
    longer ones by the promoted Prophet bundle; `model_used` and `reason` say
    which. Accuracy comes from the shipped backtest, never a live re-backtest,
    which would take minutes and could drift from what was validated.
    """
    if horizon not in VALID_HORIZONS:
        raise HTTPException(
            status_code=422,
            detail=f"horizon must be one of {', '.join(map(str, VALID_HORIZONS))}",
        )

    artifacts = request.app.state.artifacts
    metrics = artifacts.require("forecast_metrics")
    rows = artifacts.require("backtest_rows")
    model_used, reason = route_model(horizon)
    # Require what the route needs before the cache check, so a missing
    # artifact surfaces even when a payload is memoised.
    if model_used == "prophet":
        artifacts.require("forecast_model")
    else:
        artifacts.require("production_series")

    cached = _FORECAST_CACHE.get(horizon)
    if cached is not None:
        # forecast_date is the only field that can go stale within a process.
        return {**cached, "forecast_date": date.today().isoformat()}

    prophet_accuracy = _prophet_accuracy(metrics, horizon)
    naive_backtest = seasonal_naive_backtest(rows, horizon)

    payload: dict[str, Any] | None = None
    if model_used == "seasonal_naive":
        payload = _seasonal_naive_forecast(
            artifacts.require("production_series"), horizon, naive_backtest, rows
        )
        if payload is None:
            model_used, reason = "prophet", REASON_NAIVE_UNAVAILABLE
    if payload is None:
        payload = _prophet_forecast(artifacts.require("forecast_model"), horizon)

    payload["model_used"] = model_used
    payload["reason"] = reason
    payload["accuracy_at_horizon"] = _accuracy_at_horizon(
        model_used, prophet_accuracy, naive_backtest
    )
    _FORECAST_CACHE[horizon] = payload
    return payload


@router.get("/forecast/history", summary="Backtest results per horizon")
def get_forecast_history(request: Request) -> dict[str, Any]:
    """Per-horizon metrics for both models plus the per-origin rows behind them.

    Both methods are scored on the same rolling origins, so the routing choice
    in `/forecast` can be checked against the evidence rather than taken on
    trust.
    """
    artifacts = request.app.state.artifacts
    metrics = artifacts.require("forecast_metrics")
    rows = artifacts.require("backtest_rows")

    horizons = []
    for r in metrics.itertuples():
        horizon = int(r.horizon_months)
        naive = seasonal_naive_backtest(rows, horizon)
        naive_mape = float(r.naive_mape)
        better = "seasonal_naive" if naive_mape < float(r.mape) else "prophet"
        routed, _reason = route_model(horizon)
        horizons.append(
            {
                "horizon_months": horizon,
                "n_origins": int(r.n_origins),
                "mape": float(r.mape),
                "rmse": float(r.rmse),
                "naive_mape": naive_mape,
                "skill_vs_naive_pp": float(r.skill_vs_naive_pp),
                "ci80_coverage": float(r.ci80_coverage),
                "comparison": {
                    "prophet_mape": float(r.mape),
                    "seasonal_naive_mape": naive_mape,
                    "prophet_rmse": float(r.rmse),
                    "seasonal_naive_rmse": naive["rmse"] if naive else None,
                    "prophet_ci80_coverage": float(r.ci80_coverage),
                    "seasonal_naive_ci80_coverage": naive["ci80_coverage"] if naive else None,
                    "better_model": better,
                    "model_used": routed,
                    "routing_matches_backtest": routed == better,
                },
            }
        )
    origins = [
        {
            "horizon_months": int(r.horizon_months),
            "origin_month": pd.Period(r.origin_ds, freq="M").strftime("%Y-%m"),
            "target_month": pd.Period(r.target_ds, freq="M").strftime("%Y-%m"),
            "actual_tonnes": float(r.actual),
            "predicted_tonnes": float(r.predicted),
            "seasonal_naive_tonnes": float(r.naive),
            "covered": bool(r.covered),
        }
        for r in rows.itertuples()
    ]

    return {
        "horizons": horizons,
        "origins": origins,
        "model": {"version": FORECAST_MODEL_VERSION, "variant": "vanilla"},
        "benchmark": {
            "name": "seasonal_naive",
            "definition": "same calendar month one year earlier",
        },
        "routing": {
            "seasonal_naive_max_horizon": SEASONAL_NAIVE_MAX_HORIZON,
            "rule": (
                f"horizons <= {SEASONAL_NAIVE_MAX_HORIZON} months are served by "
                "seasonal_naive, longer horizons by prophet"
            ),
        },
    }


@router.get("/production/history", summary="MH+MP monthly manganese production")
def get_production_history(
    request: Request,
    start: str | None = Query(None, description="Inclusive start month, YYYY-MM"),
    end: str | None = Query(None, description="Inclusive end month, YYYY-MM"),
) -> dict[str, Any]:
    """Monthly MH+MP production from the IBM MSMP bulletins.

    Reads the 123-month parquet, not the 20-row BSE table in Supabase: the
    MSMP series is the Phase 3 source of truth and the BSE rows are kept only
    to validate the MH+MP proxy.
    """
    frame = request.app.state.artifacts.require("production_series").copy()

    def _month(value: str, name: str) -> pd.Period:
        try:
            return pd.Period(value, freq="M")
        except Exception as exc:  # noqa: BLE001 - turned into a 422 below
            raise HTTPException(
                status_code=422,
                detail=f"{name} must be a month formatted YYYY-MM, got {value!r}",
            ) from exc

    first, last = _month(start, "start") if start else None, _month(end, "end") if end else None
    if first is not None and last is not None and first > last:
        raise HTTPException(
            status_code=422, detail=f"start ({start}) must not be after end ({end})"
        )

    if first is not None:
        frame = frame[frame.report_month >= first]
    if last is not None:
        frame = frame[frame.report_month <= last]
    frame = frame.sort_values("report_month")

    series = [
        {
            "report_month": str(row.report_month),
            "mh_qty_tonnes": float(row.mh_qty_tonnes),
            "mp_qty_tonnes": float(row.mp_qty_tonnes),
            "mh_plus_mp_qty_tonnes": float(row.mh_plus_mp_qty_tonnes),
            "all_india_qty_tonnes": float(row.all_india_qty_tonnes),
            "extraction_method": "ocr" if row.extraction_method == "tesseract_ocr" else "text",
        }
        for row in frame.itertuples()
    ]

    # Coverage describes the window that was asked for, not the whole series.
    if len(frame):
        window_start = first if first is not None else frame.report_month.min()
        window_end = last if last is not None else frame.report_month.max()
        expected = pd.period_range(window_start, window_end, freq="M")
        present = set(frame.report_month)
        gaps = [str(p) for p in expected if p not in present]
        coverage = {
            "months_present": len(frame),
            "months_missing": len(gaps),
            "date_range": {"start": str(window_start), "end": str(window_end)},
            "gaps": gaps,
        }
    else:
        # An empty window is a valid state, not an error.
        coverage = {
            "months_present": 0,
            "months_missing": 0,
            "date_range": {"start": start, "end": end},
            "gaps": [],
        }

    return {
        "series": series,
        "coverage": coverage,
        "metadata": {
            "source": "IBM MSMP monthly bulletins",
            "proxy_note": (
                "MH+MP is used as proxy for MOIL operating region "
                "(~49% of India's manganese)"
            ),
        },
    }


def _run_retrain(task_id: str) -> None:
    """Background retrain of the forecasting stack."""
    task = _FORECAST_TASKS[task_id]
    task["status"] = "running"
    task["started_at"] = datetime.now(UTC)
    try:
        from src.models.forecast.prophet_baseline import main as prophet_main

        prophet_main()
        task["status"] = "completed"
        task["detail"] = "prophet baseline retrained"
    except Exception as exc:  # noqa: BLE001 - reported through the status endpoint
        task["status"] = "failed"
        task["detail"] = f"{type(exc).__name__}: {exc}"
        task["traceback"] = traceback.format_exc()
    finally:
        task["finished_at"] = datetime.now(UTC)


@router.post("/forecast/retrain", summary="Retrain the forecast model")
def retrain_forecast() -> dict[str, Any]:
    """Disabled for the demo.

    Retraining takes ~40 minutes with MCMC sampling, cannot be meaningfully
    awaited, and the previous implementation wrote to the served model path -
    the exact mechanism that put a rejected variant into production while the
    API returned 200.
    """
    raise NotImplementedInDemo(
        detail="retraining is disabled in demo mode",
        remedy=(
            "run python -m src.models.forecast.prophet_baseline locally, "
            "then promote the artifact to models/prophet_baseline_v1_0_shipped.pkl"
        ),
    )


@router.get("/forecast/retrain/{task_id}", response_model=TrainStatusOut, summary="Retrain status")
def retrain_status(task_id: str) -> TrainStatusOut:
    task = _FORECAST_TASKS.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"task {task_id} not found")
    return TrainStatusOut(
        task_id=task_id,
        status=task["status"],
        detail=task.get("detail"),
        started_at=task.get("started_at"),
        finished_at=task.get("finished_at"),
    )
