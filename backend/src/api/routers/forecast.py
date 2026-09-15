"""Production forecasting and shortfall-risk endpoints (Phase 3)."""

from __future__ import annotations

import traceback
import uuid
from datetime import UTC, date, datetime
from typing import Any

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


@router.get("/forecast", summary="Forecast MH+MP production")
def get_forecast(request: Request, horizon: int = Query(1, description=f"Months ahead. One of {VALID_HORIZONS}.")) -> dict[str, Any]:
    """Prophet forecast at one of the backtested horizons.

    Reads the promoted bundle and the shipped backtest metrics from app.state.
    `accuracy_at_horizon` is looked up in that artifact rather than recomputed:
    a live re-backtest would take minutes and could drift from the numbers the
    shipped model was actually validated with.
    """
    if horizon not in VALID_HORIZONS:
        raise HTTPException(
            status_code=422,
            detail=f"horizon must be one of {', '.join(map(str, VALID_HORIZONS))}",
        )

    artifacts = request.app.state.artifacts
    bundle = artifacts.require("forecast_model")
    metrics = artifacts.require("forecast_metrics")

    cached = _FORECAST_CACHE.get(horizon)
    if cached is not None:
        # forecast_date is the only field that can go stale within a process.
        return {**cached, "forecast_date": date.today().isoformat()}

    model, frame = bundle["model"], bundle["frame"]
    try:
        future = model.make_future_dataframe(periods=horizon, freq="MS")
        future = _future_regressors(frame, future, as_of=frame.ds.iloc[-1], full=frame)
        forecast = model.predict(future)
    except Exception as exc:  # noqa: BLE001 - surfaced with a code
        raise PredictionFailed(f"prophet prediction failed: {exc}") from exc

    row = forecast.iloc[-1]
    # One row per month of the horizon, straight from the same predict() call:
    # the months between issue and target are model output, never interpolated.
    # The bundle's interval_width is 0.80, so yhat_lower/yhat_upper are the 10th
    # and 90th percentiles of the predictive samples. p50 is Prophet's point
    # estimate (yhat), the value `predicted_tonnes` has always carried.
    series = [
        {
            "month": pd.Period(month.ds, freq="M").strftime("%Y-%m"),
            "month_label": pd.Period(month.ds, freq="M").strftime("%b %Y"),
            "p10": float(month.yhat_lower),
            "p50": float(month.yhat),
            "p90": float(month.yhat_upper),
        }
        for month in forecast.iloc[-horizon:].itertuples()
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

    at_horizon = metrics[metrics.horizon_months == horizon]
    accuracy = (
        {
            "mape": float(at_horizon.mape.iloc[0]),
            "naive_mape": float(at_horizon.naive_mape.iloc[0]),
            "skill_vs_naive_pp": float(at_horizon.skill_vs_naive_pp.iloc[0]),
            "ci80_coverage": float(at_horizon.ci80_coverage.iloc[0]),
            "rmse": float(at_horizon.rmse.iloc[0]),
            "n_origins": int(at_horizon.n_origins.iloc[0]),
        }
        if len(at_horizon)
        else None
    )

    payload = {
        "forecast_date": date.today().isoformat(),
        "target_period": pd.Period(row.ds, freq="M").strftime("%Y-%m"),
        "horizon_months": horizon,
        "predicted_tonnes": float(row.yhat),
        "predicted_lower_ci": float(row.yhat_lower),
        "predicted_upper_ci": float(row.yhat_upper),
        "ci_level": 0.80,
        "components": components,
        "model": {
            "version": FORECAST_MODEL_VERSION,
            "variant": bundle.get("variant", "vanilla"),
            "regressors": list(bundle.get("regressors") or []),
            "trained_through": pd.Period(frame.ds.max(), freq="M").strftime("%Y-%m"),
            "changepoint_prior_scale": CHANGEPOINT_PRIOR_SCALE,
            "mcmc_samples": 300,
        },
        "accuracy_at_horizon": accuracy,
        "series": series,
    }
    _FORECAST_CACHE[horizon] = payload
    return payload


@router.get("/forecast/history", summary="Backtest results per horizon")
def get_forecast_history(request: Request) -> dict[str, Any]:
    """Per-horizon metrics plus the per-origin rows behind them."""
    artifacts = request.app.state.artifacts
    metrics = artifacts.require("forecast_metrics")
    rows = artifacts.require("backtest_rows")

    horizons = [
        {
            "horizon_months": int(r.horizon_months),
            "n_origins": int(r.n_origins),
            "mape": float(r.mape),
            "rmse": float(r.rmse),
            "naive_mape": float(r.naive_mape),
            "skill_vs_naive_pp": float(r.skill_vs_naive_pp),
            "ci80_coverage": float(r.ci80_coverage),
        }
        for r in metrics.itertuples()
    ]
    origins = [
        {
            "horizon_months": int(r.horizon_months),
            "origin_month": pd.Period(r.origin_ds, freq="M").strftime("%Y-%m"),
            "target_month": pd.Period(r.target_ds, freq="M").strftime("%Y-%m"),
            "actual_tonnes": float(r.actual),
            "predicted_tonnes": float(r.predicted),
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
