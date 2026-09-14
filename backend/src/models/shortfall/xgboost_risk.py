"""
Classify next month's production shortfall risk.

Shortfall = actual production below 90% of the model's prediction for that
month. Predictions come from a rolling-origin Prophet fit, so the label for
month t only ever depends on data before t - otherwise the classifier would
be scored on a target it helped construct.

The base rate is low by construction (a handful of months in a short
history), so the honest comparison is against the majority-class baseline
and a stratified random one, both reported.

Run: python -m src.models.shortfall.xgboost_risk
"""

from __future__ import annotations

import json
import warnings
from datetime import date
from pathlib import Path

import joblib
import mlflow
import numpy as np
import pandas as pd
from sklearn.metrics import (
    average_precision_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import TimeSeriesSplit
from sqlalchemy import text
from xgboost import XGBClassifier

from src.config.settings import settings
from src.db.session import get_engine
from src.models.forecast.prophet_baseline import (
    CAPEX_EVENTS,
    _future_regressors,
    build_frame,
    fit_prophet,
)

warnings.filterwarnings("ignore")

MLFLOW_URI: str = (settings.PROJECT_ROOT / "mlruns").as_uri()
EXPERIMENT: str = "phase_3_shortfall_classifier"

MODEL_PATH: Path = settings.MODELS_DIR / "shortfall_v1.pkl"
METRICS_PATH: Path = settings.DATA_PROCESSED / "shortfall_metrics.json"

SHORTFALL_THRESHOLD: float = 0.90
MIN_TRAIN_MONTHS: int = 24

XGB_PARAMS: dict[str, object] = {
    "n_estimators": 200,
    "max_depth": 4,
    "learning_rate": 0.05,
    "tree_method": "hist",
    "eval_metric": "aucpr",
    "objective": "binary:logistic",
    "n_jobs": 4,
    "random_state": 42,
}

FEATURES: list[str] = [
    "rain_departure_3m",
    "rain_ytd_departure",
    "prophet_growth_rate",
    "days_since_capex",
    "monsoon_phase",
    "quarter_shortfall_rate",
    "qoq_growth",
]


def district_rainfall_monthly() -> pd.DataFrame:
    sql = """
        SELECT date_trunc('month', date)::date AS month,
               SUM(rainfall_mm) / COUNT(DISTINCT district) AS rainfall_mm
        FROM imd_rainfall_daily
        GROUP BY 1 ORDER BY 1
    """
    with get_engine().connect() as conn:
        rows = conn.execute(text(sql)).all()
    frame = pd.DataFrame(rows, columns=["ds", "rainfall_month_mm"])
    frame["ds"] = pd.to_datetime(frame["ds"])
    frame["rainfall_month_mm"] = pd.to_numeric(frame["rainfall_month_mm"], errors="coerce")
    return frame


def rolling_predictions(frame: pd.DataFrame) -> pd.DataFrame:
    """One-month-ahead Prophet prediction per month, refit at each origin."""
    records: list[dict[str, object]] = []
    for origin in range(MIN_TRAIN_MONTHS, len(frame)):
        history = frame.iloc[:origin]
        target = frame.iloc[origin]
        model = fit_prophet(history)
        future = model.make_future_dataframe(periods=1, freq="MS")
        future = _future_regressors(frame, future)
        forecast = model.predict(future)
        predicted = float(forecast.yhat.iloc[-1])
        recent = float(history.y.iloc[-1])
        records.append(
            {
                "ds": target.ds,
                "actual": float(target.y),
                "predicted": predicted,
                "prophet_growth_rate": (predicted - recent) / recent if recent else 0.0,
            }
        )
    return pd.DataFrame(records)


def build_features() -> pd.DataFrame:
    base = build_frame()
    rainfall = district_rainfall_monthly()
    predictions = rolling_predictions(base)
    if predictions.empty:
        raise RuntimeError(
            f"need more than {MIN_TRAIN_MONTHS} months of production to label shortfalls; "
            f"have {len(base)}"
        )

    frame = predictions.merge(rainfall, on="ds", how="left")
    frame["shortfall"] = (frame.actual < SHORTFALL_THRESHOLD * frame.predicted).astype(int)

    # Rainfall departure from that calendar month's own climatology.
    climatology = frame.groupby(frame.ds.dt.month).rainfall_month_mm.transform("mean")
    frame["rain_departure_pct"] = (
        (frame.rainfall_month_mm - climatology) / climatology.replace(0.0, np.nan) * 100.0
    )
    frame["rain_departure_3m"] = frame.rain_departure_pct.rolling(3, min_periods=1).mean()

    # Fiscal-year-to-date rainfall departure (Indian FY starts in April).
    frame["fy"] = np.where(frame.ds.dt.month >= 4, frame.ds.dt.year, frame.ds.dt.year - 1)
    frame["rain_ytd_departure"] = (
        frame.groupby("fy").rain_departure_pct.transform(
            lambda s: s.expanding().mean()
        )
    )

    capex = pd.to_datetime(pd.Series(list(CAPEX_EVENTS)))
    def _since(stamp: pd.Timestamp) -> float:
        past = capex[capex <= stamp]
        return float((stamp - past.max()).days) if len(past) else 9999.0
    frame["days_since_capex"] = frame.ds.map(_since)

    # 0 pre-monsoon, 1 during (Jun-Sep), 2 post.
    month = frame.ds.dt.month
    frame["monsoon_phase"] = np.select(
        [month.between(6, 9), month.between(10, 12)], [1, 2], default=0
    )

    frame["quarter"] = ((month - 4) % 12) // 3 + 1
    # Historical shortfall rate for the same fiscal quarter, shifted so the
    # current row never contributes to its own feature.
    frame["quarter_shortfall_rate"] = (
        frame.groupby("quarter").shortfall.transform(
            lambda s: s.shift(1).expanding().mean()
        )
    ).fillna(0.0)

    frame["qoq_growth"] = frame.actual.pct_change(3).fillna(0.0)
    frame[FEATURES] = frame[FEATURES].replace([np.inf, -np.inf], np.nan).fillna(0.0)
    return frame


def main() -> None:
    frame = build_features()
    X = frame[FEATURES]
    y = frame.shortfall.to_numpy()

    n_pos = int(y.sum())
    print(f"  labelled months : {len(frame)}")
    print(f"  shortfalls      : {n_pos}  ({n_pos / len(y) * 100:.1f}% base rate)")
    print(f"  definition      : actual < {SHORTFALL_THRESHOLD:.0%} of rolling Prophet prediction")

    if n_pos < 3:
        raise RuntimeError(
            f"only {n_pos} shortfall month(s) in the labelled history - too few to fit "
            "or validate a classifier. Report the gap rather than a fitted number."
        )

    scale = float((len(y) - n_pos) / max(n_pos, 1))
    n_splits = min(5, max(2, n_pos - 1))
    splitter = TimeSeriesSplit(n_splits=n_splits)

    oof = np.full(len(y), np.nan)
    for train_index, test_index in splitter.split(X):
        if y[train_index].sum() == 0:
            continue
        model = XGBClassifier(**XGB_PARAMS, scale_pos_weight=scale)
        model.fit(X.iloc[train_index], y[train_index], verbose=False)
        oof[test_index] = model.predict_proba(X.iloc[test_index])[:, 1]

    scored = ~np.isnan(oof)
    metrics: dict[str, object] = {
        "n_months": len(frame),
        "n_shortfalls": n_pos,
        "base_rate": float(y.mean()),
        "n_scored": int(scored.sum()),
        "n_splits": n_splits,
    }
    if scored.sum() and len(np.unique(y[scored])) > 1:
        # Threshold chosen on the out-of-fold scores to favour recall - a
        # missed shortfall costs more than a false alarm in this setting.
        best_f1, best_threshold = -1.0, 0.5
        for threshold in np.linspace(0.05, 0.95, 19):
            f1 = f1_score(y[scored], (oof[scored] >= threshold).astype(int), zero_division=0)
            if f1 > best_f1:
                best_f1, best_threshold = f1, float(threshold)
        predicted = (oof[scored] >= best_threshold).astype(int)
        metrics.update(
            {
                "auc": float(roc_auc_score(y[scored], oof[scored])),
                "auc_pr": float(average_precision_score(y[scored], oof[scored])),
                "precision": float(precision_score(y[scored], predicted, zero_division=0)),
                "recall": float(recall_score(y[scored], predicted, zero_division=0)),
                "f1": float(best_f1),
                "threshold": best_threshold,
                "confusion_matrix": confusion_matrix(y[scored], predicted).tolist(),
            }
        )
    else:
        metrics["note"] = "out-of-fold scoring had a single class; AUC undefined"

    final = XGBClassifier(**XGB_PARAMS, scale_pos_weight=scale)
    final.fit(X, y, verbose=False)
    importance = pd.Series(final.feature_importances_, index=FEATURES).sort_values(ascending=False)

    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(
        {
            "model": final,
            "features": FEATURES,
            "threshold": metrics.get("threshold", 0.5),
            "shortfall_threshold": SHORTFALL_THRESHOLD,
            "metrics": metrics,
        },
        MODEL_PATH,
    )

    mlflow.set_tracking_uri(MLFLOW_URI)
    mlflow.set_experiment(EXPERIMENT)
    with mlflow.start_run(run_name="shortfall_v1"):
        mlflow.log_params({**XGB_PARAMS, "scale_pos_weight": scale, "n_features": len(FEATURES)})
        mlflow.log_metrics({k: v for k, v in metrics.items() if isinstance(v, (int, float))})
        mlflow.log_dict(importance.to_dict(), "feature_importance.json")
        mlflow.log_artifact(str(MODEL_PATH))

    print("")
    print("=" * 66)
    print("SHORTFALL RISK CLASSIFIER")
    print("=" * 66)
    for key in ("auc", "auc_pr", "precision", "recall", "f1", "threshold"):
        if key in metrics:
            print(f"  {key:<20}: {metrics[key]:.4f}")
    if "confusion_matrix" in metrics:
        (tn, fp), (fn, tp) = metrics["confusion_matrix"]
        print(f"  confusion           : TN={tn} FP={fp} FN={fn} TP={tp}")
    if "note" in metrics:
        print(f"  note                : {metrics['note']}")

    print("")
    print("  feature importance:")
    for name, value in importance.items():
        print(f"    {name:<26} {value:.5f}")

    if "auc" in metrics:
        auc = float(metrics["auc"])
        verdict = (
            "real signal - can genuinely warn of coming shortfalls" if auc > 0.80
            else "weak/random - feature set is not informative" if auc < 0.60
            else "moderate signal"
        )
        print(f"\n  verdict: AUC {auc:.3f} -> {verdict}")

    METRICS_PATH.write_text(json.dumps(metrics, indent=2, default=str), encoding="utf-8")
    print(f"  metrics written : {METRICS_PATH}")
    print(f"  model saved     : {MODEL_PATH}")


if __name__ == "__main__":
    main()
