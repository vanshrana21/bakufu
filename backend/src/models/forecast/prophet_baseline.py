"""
Prophet forecast of manganese ore production in MOIL's operating region.

The target is Maharashtra + Madhya Pradesh monthly production from the IBM
MSMP bulletins - 123 months, Jan 2016 to May 2026. MOIL does not publish a
usable monthly series of its own (only 20 scattered months exist from BSE
press releases), so MH+MP stands in as the proxy for its operating geography.

That proxy is validated rather than assumed: over the 20 overlapping months
MH+MP correlates with MOIL substantially better than all-India does
(r 0.813 vs 0.554, ratio CV 5.9% vs 12.5%), consistent with MH+MP being
MOIL's actual operating geography. The MOIL/(MH+MP) ratio is 0.831 +/- 0.049
with no visible drift. The one OCR-recovered month in that overlap (2025-02,
ratio 0.745) sits inside the observed range, so OCR quality is not distorting
the validation.

Three variants are fitted and backtested separately, so the contribution of
each regressor is measured rather than assumed:

    vanilla    yearly seasonality only - the floor every other variant
               has to beat
    rainfall   + lagged district rainfall
    capex      + a step regressor at announced expansions

Rainfall and leakage
--------------------
IBM publishes production with roughly a two-month lag while IMD rainfall is
near-real-time, which makes it tempting - and wrong - to regress month M
production on month M rainfall. At the moment a forecast for month M is made,
month M rainfall has not happened. Only *lagged* rainfall is used here:
rain(M-1) and rain(M-2), both genuinely available at prediction time.

Lagged observed rain is preferred to climatology because it carries the
signal the mechanism implies: heavy rain floods pits and degrades haul roads,
and that effect persists into the following weeks. Climatology is just a
smooth seasonal curve that Prophet's own yearly seasonality already models,
so a climatology regressor would largely duplicate the seasonality term.

Beyond a 1-month horizon even lagged rain runs out - forecasting M+6 needs
rain(M+5), which does not exist yet - so climatology fills the unobserved
months only, and every row records which source it used. That makes
"MAPE by fraction of climatological regressor use" computable, which is the
honest way to show quality degrading across horizons.

A production deployment would replace that climatology fallback with IMD's
official seasonal forecast; wiring that in is deferred to Phase 4.

Validation is a rolling-origin backtest at 1, 3, 6 and 12 month horizons,
scored against a seasonal-naive baseline (same month last year) so the MAPE
numbers mean something rather than floating free.

Run: python -m src.models.forecast.prophet_baseline --variant vanilla
"""

from __future__ import annotations

import argparse
import json
import logging
import warnings
from datetime import date
from pathlib import Path

import joblib
import mlflow
import numpy as np
import pandas as pd
from prophet import Prophet

from src.config.settings import settings

warnings.filterwarnings("ignore")
logging.getLogger("cmdstanpy").setLevel(logging.ERROR)
logging.getLogger("prophet").setLevel(logging.ERROR)

MLFLOW_URI: str = (settings.PROJECT_ROOT / "mlruns").as_uri()
EXPERIMENT: str = "phase_3_2_forecasting"

#: The 123-month MSMP series is the source of truth. It lives on disk as
#: parquet rather than in Supabase: Phase 3.1 deliberately created no new
#: tables, and `moil_monthly_production` (20 rows, BSE press releases) is
#: kept for proxy validation only.
SERIES_PATH: Path = settings.DATA_PROCESSED / "msmp_mn_monthly_wide.parquet"
MOIL_VALIDATION_PATH: Path = settings.DATA_PROCESSED / "moil_monthly_series.parquet"

MODEL_PATH: Path = settings.MODELS_DIR / "prophet_baseline_v1.pkl"
METRICS_PATH: Path = settings.DATA_PROCESSED / "prophet_baseline_metrics.json"
BACKTEST_ROWS_PATH: Path = settings.DATA_PROCESSED / "prophet_backtest_rows.parquet"

HORIZONS: tuple[int, ...] = (1, 3, 6, 12)

#: Regressors per variant. Vanilla is deliberately empty.
VARIANTS: dict[str, tuple[str, ...]] = {
    "vanilla": (),
    "rainfall": ("rain_lag1", "rain_lag2"),
    "capex": ("rain_lag1", "rain_lag2", "capex"),
}

#: Announced MOIL expansions, used as a step regressor. Seeded with the known
#: Sept-2024 shaft expansion; extend as filings surface more.
CAPEX_EVENTS: tuple[date, ...] = (date(2024, 9, 1),)

#: Prophet needs two full seasons before a fit means anything.
MIN_TRAIN_MONTHS = 24

#: The first lockdown collapsed output to 23,611 t - 17% of the series median
#: - and left the fitted trend and multiplicative seasonal profile distorted.
#: These months are masked to NaN for fitting only: Prophet drops NaN targets
#: while keeping the row, so the time index and regressors stay intact.
COVID_MASK: tuple[str, str] = ("2020-04-01", "2020-08-01")

#: Raised from 0.05 after the vanilla backtest came in biased -7.33% on a
#: visibly rising series - a damped trend, not an unforecastable one. Chosen
#: from that diagnosis rather than searched over: tuning this on the backtest
#: that scores it would be a soft leak.
CHANGEPOINT_PRIOR_SCALE = 0.25


def load_production() -> pd.DataFrame:
    """MH+MP monthly production, the modelling target."""
    frame = pd.read_parquet(SERIES_PATH)
    out = pd.DataFrame(
        {
            "ds": frame["report_month"].dt.to_timestamp(),
            "y": pd.to_numeric(frame["mh_plus_mp_qty_tonnes"], errors="coerce"),
        }
    )
    return out.dropna().sort_values("ds").reset_index(drop=True)


def load_moil_validation() -> pd.DataFrame:
    """The 20 real MOIL months, used to sanity-check the proxy - never to fit."""
    if not MOIL_VALIDATION_PATH.exists():
        return pd.DataFrame(columns=["ds", "moil_tonnes"])
    frame = pd.read_parquet(MOIL_VALIDATION_PATH)
    return pd.DataFrame(
        {
            "ds": pd.to_datetime(frame["period_month"]),
            "moil_tonnes": pd.to_numeric(frame["tonnes"], errors="coerce"),
        }
    ).dropna()


def load_monthly_rainfall() -> pd.DataFrame:
    """Monthly mean rainfall across the four MOIL districts."""
    from sqlalchemy import text

    from src.db.session import get_engine

    sql = """
        SELECT date_trunc('month', date)::date AS month,
               AVG(rainfall_mm) * 30.0 AS rainfall_mm
        FROM imd_rainfall_daily
        GROUP BY 1
        ORDER BY 1
    """
    try:
        with get_engine().connect() as conn:
            rows = conn.execute(text(sql)).all()
    except Exception:  # rainfall is optional for the vanilla variant
        return pd.DataFrame(columns=["ds", "rainfall_mm"])
    frame = pd.DataFrame(rows, columns=["ds", "rainfall_mm"])
    frame["ds"] = pd.to_datetime(frame["ds"])
    frame["rainfall_mm"] = pd.to_numeric(frame["rainfall_mm"], errors="coerce")
    return frame


def build_frame(with_rainfall: bool = True) -> pd.DataFrame:
    """Production joined to its regressors, monthly."""
    production = load_production()
    if production.empty:
        raise RuntimeError(
            f"{SERIES_PATH.name} is empty - run "
            "python -m src.data.preprocess.parse_msmp_manganese first"
        )

    frame = production
    if with_rainfall:
        rainfall = load_monthly_rainfall()
        if not rainfall.empty:
            frame = frame.merge(rainfall, on="ds", how="left")
            climatology = frame.groupby(frame.ds.dt.month).rainfall_mm.transform("mean")
            frame["rainfall_mm"] = frame.rainfall_mm.fillna(climatology).fillna(
                frame.rainfall_mm.mean()
            )
            # Only lagged rain is ever a regressor; see the module docstring.
            frame["rain_lag1"] = frame.rainfall_mm.shift(1)
            frame["rain_lag2"] = frame.rainfall_mm.shift(2)
            month_norm = frame.groupby(frame.ds.dt.month).rainfall_mm.transform("mean")
            frame["rain_lag1"] = frame.rain_lag1.fillna(month_norm)
            frame["rain_lag2"] = frame.rain_lag2.fillna(month_norm)

    frame["capex"] = 0.0
    for event in CAPEX_EVENTS:
        frame.loc[frame.ds >= pd.Timestamp(event), "capex"] = 1.0
    return frame.reset_index(drop=True)


def _future_regressors(
    frame: pd.DataFrame,
    future: pd.DataFrame,
    as_of: pd.Timestamp | None = None,
    full: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Extend regressors over the forecast horizon.

    A lagged rainfall value for a *future* month can still be genuinely
    observed: forecasting month M from history ending M-1 needs rain(M-1) and
    rain(M-2), both of which have already happened. Looking the lags up only
    inside `history` therefore throws away exactly the information the lagged
    design exists to use, and silently substitutes climatology - which is the
    smooth seasonal curve Prophet's own yearly term already models, so the
    comparison would measure nothing.

    `full` supplies rainfall beyond the training window and `as_of` is the last
    observed month; a lag is taken from `full` when the month it refers to is
    at or before `as_of`, and from climatology otherwise. Every row records
    which, so "MAPE by fraction of climatological input" stays computable.
    """
    columns = [c for c in ("rain_lag1", "rain_lag2", "capex") if c in frame.columns]
    source = full if full is not None else frame
    merged = future.merge(source[["ds", *columns]], on="ds", how="left")

    lags = {"rain_lag1": 1, "rain_lag2": 2}
    if as_of is not None and any(c in lags for c in columns):
        observed = pd.Series(True, index=merged.index)
        for column in (c for c in columns if c in lags):
            refers_to = merged.ds - pd.DateOffset(months=lags[column])
            known = refers_to <= as_of
            # Anything the lag cannot legitimately see is blanked, then filled
            # from climatology below.
            merged.loc[~known, column] = np.nan
            observed &= known
        merged["regressor_source"] = np.where(observed, "observed", "climatology")
    else:
        merged["regressor_source"] = np.where(
            merged[columns[0]].notna() if columns else True, "observed", "climatology"
        )

    for column in columns:
        if column == "capex":
            last = float(frame.capex.iloc[-1]) if len(frame) else 0.0
            merged["capex"] = merged.capex.fillna(last)
            continue
        climatology = frame.groupby(frame.ds.dt.month)[column].mean()
        merged[column] = merged[column].fillna(merged.ds.dt.month.map(climatology))
        merged[column] = merged[column].fillna(float(frame[column].mean()))
    return merged


def mask_covid(frame: pd.DataFrame) -> pd.DataFrame:
    """Blank the first-lockdown months so they do not drag the fit."""
    out = frame.copy()
    lockdown = (out.ds >= COVID_MASK[0]) & (out.ds <= COVID_MASK[1])
    out.loc[lockdown, "y"] = np.nan
    return out


def fit_prophet(
    frame: pd.DataFrame,
    regressors: tuple[str, ...] = (),
    changepoint_prior_scale: float = CHANGEPOINT_PRIOR_SCALE,
    mcmc_samples: int = 0,
    covid_mask: bool = True,
) -> Prophet:
    model = Prophet(
        growth="linear",
        yearly_seasonality=True,
        weekly_seasonality=False,
        daily_seasonality=False,
        seasonality_mode="multiplicative",
        changepoint_prior_scale=changepoint_prior_scale,
        interval_width=0.80,
        mcmc_samples=mcmc_samples,
    )
    for name in regressors:
        model.add_regressor(name)
    training = mask_covid(frame) if covid_mask else frame
    model.fit(training[["ds", "y", *regressors]])
    return model


def mape(actual: np.ndarray, predicted: np.ndarray) -> float:
    actual = np.asarray(actual, dtype="float64")
    predicted = np.asarray(predicted, dtype="float64")
    keep = actual != 0
    if not keep.any():
        return float("nan")
    return float(np.mean(np.abs((actual[keep] - predicted[keep]) / actual[keep])) * 100.0)


def rmse(actual: np.ndarray, predicted: np.ndarray) -> float:
    return float(np.sqrt(np.mean((np.asarray(actual) - np.asarray(predicted)) ** 2)))


def backtest(
    frame: pd.DataFrame,
    horizons: tuple[int, ...] = HORIZONS,
    regressors: tuple[str, ...] = (),
    **fit_kwargs: object,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Rolling-origin backtest over the last 20% of history.

    At each origin the model is refit on data up to that point only, so no
    future information reaches a forecast. Targets are located by calendar
    date rather than row offset, because the series has two missing months
    and row arithmetic would silently mis-date the target across a gap.
    """
    n = len(frame)
    split = int(n * 0.8)
    by_date = frame.set_index("ds")
    rows: list[dict[str, object]] = []
    detail_rows: list[dict[str, object]] = []

    for horizon in horizons:
        records: list[dict[str, float]] = []
        for origin in range(split, n):
            history = frame.iloc[:origin]
            if len(history) < MIN_TRAIN_MONTHS:
                continue
            target_ds = history.ds.iloc[-1] + pd.DateOffset(months=horizon)
            if target_ds not in by_date.index:
                continue  # the month is one of the two gaps
            actual = float(by_date.loc[target_ds, "y"])

            model = fit_prophet(history, regressors, **fit_kwargs)  # type: ignore[arg-type]
            future = model.make_future_dataframe(periods=horizon, freq="MS")
            future = _future_regressors(
                history, future, as_of=history.ds.iloc[-1], full=frame
            )
            forecast = model.predict(future)
            predicted = float(forecast.yhat.iloc[-1])
            lower = float(forecast.yhat_lower.iloc[-1])
            upper = float(forecast.yhat_upper.iloc[-1])
            source = str(future.regressor_source.iloc[-1]) if regressors else "none"

            previous_ds = target_ds - pd.DateOffset(years=1)
            naive = (
                float(by_date.loc[previous_ds, "y"])
                if previous_ds in by_date.index
                else float(history.y.iloc[-1])
            )

            records.append(
                {
                    "actual": actual,
                    "predicted": predicted,
                    "naive": naive,
                    "covered": float(lower <= actual <= upper),
                }
            )
            detail_rows.append(
                {
                    "horizon_months": horizon,
                    "origin_ds": history.ds.iloc[-1],
                    "target_ds": target_ds,
                    "actual": actual,
                    "predicted": predicted,
                    "naive": naive,
                    "covered": bool(lower <= actual <= upper),
                    "regressor_source": source,
                }
            )

        if not records:
            continue
        detail = pd.DataFrame(records)
        rows.append(
            {
                "horizon_months": horizon,
                "n_origins": len(detail),
                "mape": mape(detail.actual, detail.predicted),
                "rmse": rmse(detail.actual, detail.predicted),
                "naive_mape": mape(detail.actual, detail.naive),
                "ci80_coverage": float(detail.covered.mean() * 100.0),
            }
        )

    results = pd.DataFrame(rows)
    if not results.empty:
        # Percentage-point gain, not a ratio: "beats naive by N pp of MAPE".
        results["skill_vs_naive_pp"] = results.naive_mape - results.mape
    return results, pd.DataFrame(detail_rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--variant", choices=sorted(VARIANTS), default="vanilla")
    parser.add_argument("--mcmc-samples", type=int, default=0,
                        help="0 uses Prophet's analytical intervals; 300 samples the posterior")
    parser.add_argument("--tag", default="", help="suffix for the MLflow run name")
    args = parser.parse_args()

    fit_options: dict[str, object] = {
        "changepoint_prior_scale": CHANGEPOINT_PRIOR_SCALE,
        "mcmc_samples": args.mcmc_samples,
        "covid_mask": True,
    }

    regressors = VARIANTS[args.variant]
    frame = build_frame(with_rainfall=bool(regressors))

    print(f"  variant          : {args.variant}{args.tag}")
    print(f"  cps / mcmc       : {CHANGEPOINT_PRIOR_SCALE} / {args.mcmc_samples}")
    print(f"  regressors       : {', '.join(regressors) if regressors else '(none)'}")
    print(f"  months available : {len(frame)}")
    print(f"  range            : {frame.ds.min().date()} .. {frame.ds.max().date()}")
    print(f"  mean production  : {frame.y.mean():,.0f} t/month")

    mlflow.set_tracking_uri(MLFLOW_URI)
    mlflow.set_experiment(EXPERIMENT)

    results, detail = backtest(frame, regressors=regressors, **fit_options)
    model = fit_prophet(frame, regressors, **fit_options)  # type: ignore[arg-type]

    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(
        {
            "model": model,
            "frame": frame,
            "variant": args.variant,
            "regressors": list(regressors),
            "capex_events": list(CAPEX_EVENTS),
        },
        MODEL_PATH,
    )
    if not detail.empty:
        detail.to_parquet(BACKTEST_ROWS_PATH, index=False)

    run_name = f"prophet_{args.variant}{args.tag}"
    with mlflow.start_run(run_name=run_name):
        mlflow.log_params(
            {
                "variant": args.variant,
                "growth": "linear",
                "seasonality_mode": "multiplicative",
                "changepoint_prior_scale": CHANGEPOINT_PRIOR_SCALE,
                "mcmc_samples": args.mcmc_samples,
                "covid_mask": f"{COVID_MASK[0]}..{COVID_MASK[1]}",
                "regressors": ",".join(regressors) or "none",
                "n_months": len(frame),
                "interval_width": 0.80,
                "target": "mh_plus_mp_qty_tonnes",
                "horizons": ",".join(str(h) for h in HORIZONS),
            }
        )
        for row in results.itertuples():
            suffix = f"h{row.horizon_months}"
            mlflow.log_metrics(
                {
                    f"mape_{suffix}": row.mape,
                    f"rmse_{suffix}": row.rmse,
                    f"naive_mape_{suffix}": row.naive_mape,
                    f"ci80_coverage_{suffix}": row.ci80_coverage,
                    f"skill_vs_naive_pp_{suffix}": row.skill_vs_naive_pp,
                }
            )
        mlflow.log_artifact(str(MODEL_PATH))
        if BACKTEST_ROWS_PATH.exists():
            mlflow.log_artifact(str(BACKTEST_ROWS_PATH))

    print()
    print("=" * 74)
    print(f"PROPHET ({args.variant.upper()}) - ROLLING BACKTEST")
    print("=" * 74)
    print(
        "horizon".ljust(10)
        + "origins".rjust(9)
        + "MAPE%".rjust(9)
        + "naive%".rjust(9)
        + "skill pp".rjust(10)
        + "RMSE".rjust(11)
        + "CI80%".rjust(9)
    )
    print("-" * 74)
    for row in results.itertuples():
        print(
            f"{row.horizon_months:>2}-month".ljust(10)
            + f"{row.n_origins:>9}"
            + f"{row.mape:>9.2f}"
            + f"{row.naive_mape:>9.2f}"
            + f"{row.skill_vs_naive_pp:>10.2f}"
            + f"{row.rmse:>11,.0f}"
            + f"{row.ci80_coverage:>9.1f}"
        )

    METRICS_PATH.write_text(results.to_json(orient="records", indent=2), encoding="utf-8")
    print()
    print(f"  metrics written : {METRICS_PATH}")
    print(f"  model saved     : {MODEL_PATH}")


if __name__ == "__main__":
    main()
