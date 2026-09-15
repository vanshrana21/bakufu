"""Shortfall-risk endpoint (Phase 3.2d classifier, Phase 4 wiring)."""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from fastapi import APIRouter, Request

from src.api.errors import DataNotLoaded, PredictionFailed
from src.api.state import SHORTFALL_MODEL_VERSION
from src.config.settings import settings

logger = logging.getLogger("api.shortfall")

router = APIRouter(tags=["forecast"])

#: A cold call is ~6.6s - the SHAP explainer dominates - against a 500ms
#: target. Inputs are immutable for the life of the process, so the payload is
#: memoised in-process and also persisted: an API restart mid-demo would
#: otherwise pay the 6.6s again as a visible hang.
_RISK_CACHE: dict[str, Any] = {}

CACHE_DIR: Path = settings.DATA_PROCESSED.parent / "cache"
CACHE_TTL_SECONDS = 24 * 3600


def clear_shortfall_cache() -> None:
    _RISK_CACHE.clear()


def _cache_path(as_of: str, forecast_month: str) -> Path:
    """Keyed on both months so a new MSMP month correctly misses."""
    return CACHE_DIR / f"shortfall_{as_of}_{forecast_month}.json"


def _disk_read(as_of: str, forecast_month: str) -> dict[str, Any] | None:
    path = _cache_path(as_of, forecast_month)
    if not path.exists() or time.time() - path.stat().st_mtime > CACHE_TTL_SECONDS:
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 - a corrupt file just misses the cache
        return None


def _disk_write(payload: dict[str, Any]) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    try:
        _cache_path(payload["as_of"], payload["forecast_month"]).write_text(
            json.dumps(payload), encoding="utf-8"
        )
    except Exception:  # noqa: BLE001 - caching is an optimisation, never fatal
        logger.warning("could not persist shortfall cache")

#: Human labels so the frontend renders an explanation, not variable names.
FEATURE_LABELS: dict[str, str] = {
    "deviation_lag1": "Last month vs forecast",
    "deviation_lag2": "Two months ago vs forecast",
    "rainfall_concurrent_mm": "Rainfall this month",
    "rainfall_lag1_mm": "Rainfall last month",
    "rainfall_lag2_mm": "Rainfall 2 months ago",
    "month_sin": "Season (cyclical)",
    "month_cos": "Season (cyclical)",
    "production_trend_3mo": "3-month production trend",
    "prophet_forecast_level": "Forecast production level",
}


def _display_value(name: str, value: float) -> str:
    """A renderable string - a raw 0.074 means nothing in a UI."""
    if name.startswith("deviation"):
        return f"{value * 100:+.1f}%"
    if name.startswith("rainfall"):
        return f"{value:,.1f} mm"
    if name == "production_trend_3mo":
        return f"{(value - 1) * 100:+.1f}% vs prior quarter"
    if name == "prophet_forecast_level":
        return f"{value:,.0f} t"
    return f"{value:.3f}"


def _build_row(
    history: pd.DataFrame,
    actual: pd.Series,
    rainfall: pd.Series,
    target: pd.Timestamp,
    level: float,
) -> dict[str, float]:
    """The nine features for the target month, all causally available."""

    def lag(series: pd.Series, months: int) -> float:
        return float(series.loc[target - pd.DateOffset(months=months)])

    return {
        "deviation_lag1": float(history.deviation.iloc[-1]),
        "deviation_lag2": float(history.deviation.iloc[-2]),
        "rainfall_concurrent_mm": float(rainfall.loc[target]),
        "rainfall_lag1_mm": lag(rainfall, 1),
        "rainfall_lag2_mm": lag(rainfall, 2),
        "month_sin": float(np.sin(2 * np.pi * target.month / 12)),
        "month_cos": float(np.cos(2 * np.pi * target.month / 12)),
        "production_trend_3mo": float(
            np.mean([lag(actual, k) for k in (1, 2, 3)])
            / np.mean([lag(actual, k) for k in (4, 5, 6)])
        ),
        "prophet_forecast_level": level,
    }


@router.get("/shortfall/risk", summary="Next month's shortfall risk")
def get_shortfall_risk(request: Request) -> dict[str, Any]:
    """Probability that next month falls below 90% of the Prophet forecast.

    Scores the next *unobserved* month rather than re-scoring the last
    historical one. Every feature for it is genuinely available at prediction
    time: IMD publishes rainfall near-real-time, so the concurrent month is
    known, and the deviations come from months already published.
    """
    import shap

    from src.models.forecast.prophet_baseline import load_monthly_rainfall
    from src.models.shortfall_classifier import SHORTFALL_THRESHOLD

    artifacts = request.app.state.artifacts
    bundle = artifacts.require("shortfall_model")
    if "payload" in _RISK_CACHE:
        return _RISK_CACHE["payload"]
    features_frame = artifacts.require("shortfall_features")
    forecast_bundle = artifacts.require("forecast_model")

    try:
        history = features_frame.sort_values("ds").reset_index(drop=True)
        last_observed = history.ds.iloc[-1]
        target = last_observed + pd.DateOffset(months=1)

        as_of_key = pd.Period(last_observed, freq="M").strftime("%Y-%m")
        target_key = pd.Period(target, freq="M").strftime("%Y-%m")
        persisted = _disk_read(as_of_key, target_key)
        if persisted is not None:
            _RISK_CACHE["payload"] = persisted
            return persisted

        rainfall_frame = load_monthly_rainfall()
        if rainfall_frame.empty:
            # load_monthly_rainfall() swallows a DB failure and returns an
            # empty frame, so the first lag lookup below would raise a bare
            # KeyError naming a Timestamp - which tells nobody what is wrong.
            raise DataNotLoaded(
                detail="rainfall data unavailable - check DATABASE_URL in .env",
                remedy=(
                    "three of the classifier's nine features are rainfall terms, "
                    "read from imd_rainfall_daily; see .env.example"
                ),
            )
        rainfall = rainfall_frame.set_index("ds").rainfall_mm
        # Provenance is recorded because a silent climatology fallback produced
        # a false null in Phase 3.2c; if this ever reads imputed, the
        # explanation is weaker and the UI should say so.
        rain_source = "observed" if target in rainfall.index else "imputed_climatology"
        if rain_source == "imputed_climatology":
            same_month = [v for d, v in rainfall.items() if d.month == target.month]
            rainfall.loc[target] = float(np.mean(same_month)) if same_month else 0.0

        prophet_model = forecast_bundle["model"]
        level = float(prophet_model.predict(pd.DataFrame({"ds": [target]})).yhat.iloc[0])
        actual = forecast_bundle["frame"].set_index("ds").y

        row = _build_row(history, actual, rainfall, target, level)
        order = list(bundle["features"])
        design = pd.DataFrame([row])[order]
        probability = float(bundle["model"].predict_proba(design)[:, 1][0])

        from src.models.prospectivity.explain import _explainer
        explainer = _explainer(bundle)
        contributions = explainer.shap_values(design)[0]
        base_value = float(np.ravel(explainer.expected_value)[0])
    except DataNotLoaded:
        raise  # already carries a specific, actionable message
    except Exception as exc:  # noqa: BLE001 - surfaced with a machine code
        raise PredictionFailed(f"shortfall scoring failed: {exc}") from exc

    # All nine, sorted by magnitude. The API does not decide how many the UI
    # shows, and base + sum(contributions) reconciles to the probability, so a
    # waterfall chart adds up.
    ranked = sorted(
        (
            {
                "feature_name": name,
                "human_label": FEATURE_LABELS.get(name, name),
                "value": float(row[name]),
                "display_value": _display_value(name, float(row[name])),
                "shap_contribution": float(value),
                "direction": "increases_risk" if value > 0 else "decreases_risk",
            }
            for name, value in zip(order, contributions)
        ),
        key=lambda item: abs(item["shap_contribution"]),
        reverse=True,
    )

    risk_level = "high" if probability >= 0.50 else "medium" if probability >= 0.25 else "low"

    payload = {
        "as_of": pd.Period(last_observed, freq="M").strftime("%Y-%m"),
        "forecast_month": pd.Period(target, freq="M").strftime("%Y-%m"),
        "shortfall_probability": probability,
        "risk_level": risk_level,
        "shortfall_definition": (
            "actual production below 90% of the Prophet forecast for that month"
        ),
        "prophet_forecast_tonnes": level,
        "shortfall_threshold_tonnes": level * SHORTFALL_THRESHOLD,
        "feature_contributions": ranked,
        "shap_base_value": base_value,
        "feature_provenance": {
            "rainfall": rain_source,
            "prophet_forecast": "shipped_model",
        },
        "model_metadata": {
            "version": SHORTFALL_MODEL_VERSION,
            # From the Phase 3.2d backtest, not recomputed per request.
            "base_rate": 0.217,
            "roc_auc": 0.749,
            "pr_auc": 0.344,
            "trained_on_months": int(bundle.get("n_train", 0)),
            "trained_on_positives": int(bundle.get("n_positives", 0)),
            "decision_threshold": 0.5,
        },
    }
    _RISK_CACHE["payload"] = payload
    _disk_write(payload)
    return payload
