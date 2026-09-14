"""
Predict the probability that a month's production falls short of forecast.

A shortfall is actual production below 90% of Prophet's forecast for that
month. The dashboard wants a risk score, not another point forecast: "how
likely is this month to disappoint" is a different question from "how much
will this month produce", and a model can be useful on one and useless on
the other.

Labels come from a rolling-origin Prophet backtest, never an in-sample fit.
An in-sample forecast has already seen the month it is being scored on, so
the residual it produces is shrunken towards zero and the resulting label
would be partly a function of the answer. The origin sweep therefore starts
at month 25 - the first point where Prophet has two seasons of history -
rather than at the 80% split the level-forecast backtest uses. Starting at
the 80% split would leave roughly 25 labelled months and, at the expected
base rate, only two to four positives: too few to train or to score.

Every feature is causally available when the prediction is made. Rainfall is
the one that could silently degrade - if a month is missing it gets imputed
from climatology - so each row carries a provenance column recording whether
its rainfall was observed or imputed. In Phase 3.2c a missing provenance
column let a regressor quietly fall back to climatology and produce a null
result that looked real; the column exists so that cannot happen unnoticed.

Run: python -m src.models.shortfall_classifier --labels-only
"""

from __future__ import annotations

import argparse
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

from src.config.settings import settings
from src.models.forecast.prophet_baseline import (
    CHANGEPOINT_PRIOR_SCALE,
    MIN_TRAIN_MONTHS,
    build_frame,
    fit_prophet,
)

warnings.filterwarnings("ignore")

LABELS_PATH: Path = settings.DATA_PROCESSED / "shortfall_labels.parquet"
FEATURES_PATH: Path = settings.DATA_PROCESSED / "shortfall_features.parquet"
RESULTS_PATH: Path = settings.DATA_PROCESSED / "shortfall_backtest.parquet"
SHAP_PATH: Path = settings.DATA_PROCESSED / "shortfall_shap.png"
MODEL_PATH: Path = settings.MODELS_DIR / "shortfall_classifier_v1.pkl"

#: Actual below this fraction of forecast counts as a shortfall.
SHORTFALL_THRESHOLD = 0.90

#: Prophet forecasts poorly on short training windows, which manufactures
#: shortfalls reflecting model immaturity rather than production weakness:
#: the 2018 label rate is 54.5% against 17.1% once the model is mature.
#: Training on those would teach the classifier to detect a young Prophet.
#: The cut also excludes 2020-03..07, so COVID-scale shocks are absent from
#: the training data entirely - a scope limit, recorded rather than hidden.
MIN_TRAIN_FOR_LABEL = 60

FEATURES: tuple[str, ...] = (
    "deviation_lag1",
    "deviation_lag2",
    "rainfall_concurrent_mm",
    "rainfall_lag1_mm",
    "rainfall_lag2_mm",
    "month_sin",
    "month_cos",
    "production_trend_3mo",
    "prophet_forecast_level",
)

XGB_PARAMS: dict[str, object] = {
    "n_estimators": 200,
    "max_depth": 4,
    "learning_rate": 0.05,
    "objective": "binary:logistic",
    "eval_metric": "logloss",
    "random_state": 42,
}

#: All three must hold for the classifier to ship.
MIN_F1_GAIN_OVER_MAJORITY = 0.05
MIN_F1_GAIN_OVER_HEURISTIC = 0.03
MIN_TRUE_POSITIVES = 5


def rolling_origin_forecasts(
    frame: pd.DataFrame, min_train: int = MIN_TRAIN_MONTHS
) -> pd.DataFrame:
    """One-step-ahead forecasts, each fitted only on data before its target.

    Analytical intervals are used rather than MCMC: only the point forecast
    feeds the labels, and MCMC would turn a three-minute pass into an hour.
    """
    rows: list[dict[str, object]] = []
    for origin in range(min_train, len(frame)):
        history = frame.iloc[:origin]
        target = frame.iloc[origin]
        expected_ds = history.ds.iloc[-1] + pd.DateOffset(months=1)
        if target.ds != expected_ds:
            continue  # a gap month - the next row is not one step ahead

        model = fit_prophet(
            history,
            (),
            changepoint_prior_scale=CHANGEPOINT_PRIOR_SCALE,
            mcmc_samples=0,
        )
        future = model.make_future_dataframe(periods=1, freq="MS")
        forecast = model.predict(future)
        rows.append(
            {
                "ds": target.ds,
                "actual": float(target.y),
                "forecast": float(forecast.yhat.iloc[-1]),
                "n_train": len(history),
            }
        )
    return pd.DataFrame(rows)


def label_shortfalls(forecasts: pd.DataFrame) -> pd.DataFrame:
    frame = forecasts.copy()
    frame["deviation"] = (frame.actual - frame.forecast) / frame.forecast
    frame["shortfall"] = (frame.actual < SHORTFALL_THRESHOLD * frame.forecast).astype(int)
    return frame


def build_features(labels: pd.DataFrame, production: pd.DataFrame) -> pd.DataFrame:
    """Assemble the causal feature table.

    Every value is knowable when the month is predicted: deviations come from
    months already published, rainfall from IMD (near-real-time, so the
    concurrent month is legitimately available), and the Prophet level is the
    forecast being judged. `rainfall_source` records observed vs imputed, so
    an imputation cannot quietly masquerade as signal - the failure mode that
    produced a false null in 3.2c.
    """
    from src.models.forecast.prophet_baseline import load_monthly_rainfall

    frame = labels.sort_values("ds").reset_index(drop=True).copy()

    rainfall = load_monthly_rainfall()
    if rainfall.empty:
        raise RuntimeError(
            "rainfall unavailable - the classifier needs it; check DATABASE_URL"
        )
    frame = frame.merge(rainfall, on="ds", how="left")
    frame["rainfall_source"] = np.where(
        frame.rainfall_mm.notna(), "observed", "imputed_climatology"
    )
    climatology = frame.groupby(frame.ds.dt.month).rainfall_mm.transform("mean")
    frame["rainfall_mm"] = frame.rainfall_mm.fillna(climatology)

    frame["deviation_lag1"] = frame.deviation.shift(1)
    frame["deviation_lag2"] = frame.deviation.shift(2)
    frame["rainfall_concurrent_mm"] = frame.rainfall_mm
    frame["rainfall_lag1_mm"] = frame.rainfall_mm.shift(1)
    frame["rainfall_lag2_mm"] = frame.rainfall_mm.shift(2)

    month = frame.ds.dt.month
    frame["month_sin"] = np.sin(2 * np.pi * month / 12)
    frame["month_cos"] = np.cos(2 * np.pi * month / 12)

    actual = production.set_index("ds").y
    recent = pd.concat(
        [actual.reindex(frame.ds - pd.DateOffset(months=k)).reset_index(drop=True) for k in (1, 2, 3)],
        axis=1,
    ).mean(axis=1)
    older = pd.concat(
        [actual.reindex(frame.ds - pd.DateOffset(months=k)).reset_index(drop=True) for k in (4, 5, 6)],
        axis=1,
    ).mean(axis=1)
    frame["production_trend_3mo"] = (recent / older).values
    frame["prophet_forecast_level"] = frame.forecast

    return frame.dropna(subset=list(FEATURES)).reset_index(drop=True)


def stratified_windows(
    frame: pd.DataFrame, n_windows: int = 5, min_positives: int = 2, min_train: int = 20
) -> list[tuple[int, int]]:
    """Contiguous holdout windows, each carrying at least `min_positives`.

    Equal-width windows leave some holdouts with no positive at all, and F1
    is undefined there - the metric series would have holes exactly where the
    rare class lives.
    """
    positives = [i for i in frame.index[frame.shortfall == 1] if i >= min_train]
    if len(positives) < n_windows * min_positives:
        n_windows = max(1, len(positives) // min_positives)

    windows: list[tuple[int, int]] = []
    start = min_train
    for index, group in enumerate(np.array_split(np.array(positives), n_windows)):
        if not len(group):
            continue
        end = len(frame) if index == n_windows - 1 else int(group[-1]) + 1
        windows.append((start, end))
        start = end
    return windows


#: A month counts as recently under-performing below this deviation.
PERSISTENCE_THRESHOLD = -0.10


def persistence_heuristic(frame: pd.DataFrame, lags: int = 1) -> np.ndarray:
    """Flag a month when the previous one - or either of the previous two -
    already undershot its forecast by more than 10%.

    This is the control the classifier has to earn its place against. An
    earlier version flagged months where Prophet *predicted* a drop, which is
    close to orthogonal to the label (actual undershooting Prophet): it scored
    F1 0.000 with zero true positives, so beating it proved nothing. These
    rules operate on the same quantity the label is built from, and are the
    obvious thing a competent analyst would try before reaching for XGBoost.
    """
    flag = frame.deviation_lag1.values < PERSISTENCE_THRESHOLD
    if lags >= 2:
        flag = flag | (frame.deviation_lag2.values < PERSISTENCE_THRESHOLD)
    return flag.astype(int)


def confusion(actual: np.ndarray, predicted: np.ndarray) -> dict[str, int]:
    actual = np.asarray(actual).astype(int)
    predicted = np.asarray(predicted).astype(int)
    return {
        "tp": int(((actual == 1) & (predicted == 1)).sum()),
        "fp": int(((actual == 0) & (predicted == 1)).sum()),
        "tn": int(((actual == 0) & (predicted == 0)).sum()),
        "fn": int(((actual == 1) & (predicted == 0)).sum()),
    }


def scores(actual: np.ndarray, predicted: np.ndarray) -> dict[str, float]:
    from sklearn.metrics import f1_score, precision_score, recall_score

    return {
        "f1": float(f1_score(actual, predicted, zero_division=0)),
        "precision": float(precision_score(actual, predicted, zero_division=0)),
        "recall": float(recall_score(actual, predicted, zero_division=0)),
    }


def backtest_classifier(frame: pd.DataFrame) -> tuple[pd.DataFrame, list[tuple[int, int]]]:
    """Walk forward over stratified windows, training strictly on earlier months."""
    from xgboost import XGBClassifier

    windows = stratified_windows(frame)
    rows: list[dict[str, object]] = []
    for start, end in windows:
        train, test = frame.iloc[:start], frame.iloc[start:end]
        if train.shortfall.nunique() < 2 or test.empty:
            continue
        negatives = int((train.shortfall == 0).sum())
        positives = int((train.shortfall == 1).sum())
        model = XGBClassifier(**XGB_PARAMS, scale_pos_weight=negatives / max(positives, 1))
        model.fit(train[list(FEATURES)], train.shortfall)
        probability = model.predict_proba(test[list(FEATURES)])[:, 1]
        for offset, row in enumerate(test.itertuples()):
            rows.append(
                {
                    "ds": row.ds,
                    "actual": int(row.shortfall),
                    "probability": float(probability[offset]),
                    "predicted": int(probability[offset] >= 0.5),
                    "window": f"{start}:{end}",
                    "n_train": len(train),
                    "train_positives": positives,
                }
            )
    return pd.DataFrame(rows), windows


def ship_model(outcome: dict[str, object]) -> None:
    """Persist the classifier and log the run - only if the criterion held.

    The pickle is written only on a pass, so a failing model cannot be picked
    up by the API by accident. The MLflow run is logged either way, because a
    rejected model is part of the record.
    """
    import joblib
    import mlflow
    import shap
    from xgboost import XGBClassifier

    from src.models.forecast.prophet_baseline import EXPERIMENT, MLFLOW_URI

    features: pd.DataFrame = outcome["features"]  # type: ignore[assignment]
    table: pd.DataFrame = outcome["table"]  # type: ignore[assignment]
    ship = bool(outcome["ship"])

    X, y = features[list(FEATURES)], features.shortfall
    negatives, positives = int((y == 0).sum()), int((y == 1).sum())
    model = XGBClassifier(**XGB_PARAMS, scale_pos_weight=negatives / max(positives, 1))
    model.fit(X, y)

    values = shap.TreeExplainer(model).shap_values(X)
    importance = (
        pd.DataFrame({"feature": FEATURES, "mean_abs_shap": np.abs(values).mean(axis=0)})
        .sort_values("mean_abs_shap", ascending=False)
        .reset_index(drop=True)
    )

    mlflow.set_tracking_uri(MLFLOW_URI)
    mlflow.set_experiment(EXPERIMENT)
    with mlflow.start_run(run_name="shortfall_classifier_v1"):
        mlflow.log_params(
            {
                **{k: v for k, v in XGB_PARAMS.items() if k != "objective"},
                "shortfall_threshold": SHORTFALL_THRESHOLD,
                "min_train_for_label": MIN_TRAIN_FOR_LABEL,
                "n_months": len(features),
                "n_positives": positives,
                "scale_pos_weight": round(negatives / max(positives, 1), 3),
                "features": ",".join(FEATURES),
            }
        )
        for row in table.itertuples():
            prefix = row.model.replace("-", "_")
            mlflow.log_metrics(
                {
                    f"{prefix}_f1": row.f1,
                    f"{prefix}_precision": row.precision,
                    f"{prefix}_recall": row.recall,
                    f"{prefix}_tp": row.tp,
                    f"{prefix}_fp": row.fp,
                    f"{prefix}_tn": row.tn,
                    f"{prefix}_fn": row.fn,
                }
            )
        mlflow.log_metrics(
            {
                "roc_auc": float(outcome["auc"]),  # type: ignore[arg-type]
                "pr_auc": float(outcome["pr_auc"]),  # type: ignore[arg-type]
                "shipped": float(ship),
            }
        )
        for name, gain in outcome["gains"].items():  # type: ignore[union-attr]
            mlflow.log_metric(f"f1_gain_vs_{name.replace('-', '_')}", float(gain))
        if SHAP_PATH.exists():
            mlflow.log_artifact(str(SHAP_PATH))
        if RESULTS_PATH.exists():
            mlflow.log_artifact(str(RESULTS_PATH))

        if ship:
            MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
            joblib.dump(
                {
                    "model": model,
                    "features": list(FEATURES),
                    "shortfall_threshold": SHORTFALL_THRESHOLD,
                    "min_train_for_label": MIN_TRAIN_FOR_LABEL,
                    "shap_importance": importance,
                    "n_train": len(features),
                    "n_positives": positives,
                },
                MODEL_PATH,
            )
            mlflow.log_artifact(str(MODEL_PATH))
            print(f"  model saved     : {MODEL_PATH}")
        else:
            print("  ship criterion not met - no pickle written")

    print("\n  SHAP importance:")
    for row in importance.itertuples():
        print(f"    {row.Index + 1:>2}. {row.feature:<26} {row.mean_abs_shap:.4f}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--labels-only", action="store_true")
    args = parser.parse_args()

    frame = build_frame(with_rainfall=False)
    forecasts = rolling_origin_forecasts(frame)
    labels = label_shortfalls(forecasts)
    labels.to_parquet(LABELS_PATH, index=False)

    positives = int(labels.shortfall.sum())
    print("=" * 70)
    print("SHORTFALL LABELS - rolling-origin, one step ahead")
    print("=" * 70)
    print(f"  labelled months : {len(labels)}")
    print(f"  span            : {labels.ds.min().date()} .. {labels.ds.max().date()}")
    print(f"  positives       : {positives}")
    print(f"  base rate       : {positives / len(labels) * 100:.1f}%")
    print(f"  threshold       : actual < {SHORTFALL_THRESHOLD:.0%} of forecast")
    print(f"  labels written  : {LABELS_PATH}")

    if positives:
        print("\n  shortfall months:")
        for row in labels[labels.shortfall == 1].itertuples():
            print(
                f"    {row.ds.date()}  actual {row.actual:>10,.0f}  "
                f"forecast {row.forecast:>10,.0f}  {row.deviation * 100:>7.1f}%"
            )

    if positives < 8:
        print(
            f"\n  WARNING: {positives} positives is below the agreed floor of 8. "
            "Consider lowering the threshold to 0.85."
        )
    if args.labels_only:
        return

    outcome = evaluate(labels, frame)
    if outcome:
        ship_model(outcome)


def evaluate(labels: pd.DataFrame, production: pd.DataFrame) -> dict[str, object]:
    """Train, backtest and apply the pre-registered ship criterion."""
    from sklearn.metrics import average_precision_score, roc_auc_score

    clean = labels[labels.n_train >= MIN_TRAIN_FOR_LABEL].reset_index(drop=True)
    features = build_features(clean, production)
    features.to_parquet(FEATURES_PATH, index=False)

    imputed = int((features.rainfall_source != "observed").sum())
    print()
    print("=" * 70)
    print("SHORTFALL CLASSIFIER")
    print("=" * 70)
    print(f"  usable months   : {len(features)}  (n_train >= {MIN_TRAIN_FOR_LABEL})")
    print(f"  positives       : {int(features.shortfall.sum())}"
          f"  base rate {features.shortfall.mean() * 100:.1f}%")
    print(f"  rainfall imputed: {imputed}/{len(features)} rows")

    results, windows = backtest_classifier(features)
    if results.empty:
        print("  no usable backtest windows")
        return {}
    results.to_parquet(RESULTS_PATH, index=False)

    print(f"\n  windows ({len(windows)}):")
    for start, end in windows:
        block = features.iloc[start:end]
        print(f"    rows {start:>3}-{end:<3}  {len(block):>2} months  "
              f"{int(block.shortfall.sum())} positives  "
              f"{block.ds.min().date()}..{block.ds.max().date()}")

    actual = results.actual.to_numpy()
    # Align the heuristics to exactly the rows that were held out, by date,
    # rather than by positional slicing.
    scored = features.set_index("ds").loc[results.ds].reset_index()
    rows = []
    for name, prediction in (
        ("classifier", results.predicted.to_numpy()),
        ("majority-class", np.zeros_like(actual)),
        ("persistence-1lag", persistence_heuristic(scored, lags=1)),
        ("persistence-2lag", persistence_heuristic(scored, lags=2)),
    ):
        rows.append({"model": name, **scores(actual, prediction), **confusion(actual, prediction)})
    table = pd.DataFrame(rows)

    print(f"\n  {'model':<20}{'F1':>7}{'prec':>7}{'recall':>8}{'TP':>5}{'FP':>5}{'TN':>5}{'FN':>5}")
    print("  " + "-" * 62)
    for row in table.itertuples():
        print(f"  {row.model:<20}{row.f1:>7.3f}{row.precision:>7.3f}{row.recall:>8.3f}"
              f"{row.tp:>5}{row.fp:>5}{row.tn:>5}{row.fn:>5}")

    auc = roc_auc_score(actual, results.probability) if actual.sum() else float("nan")
    pr_auc = average_precision_score(actual, results.probability) if actual.sum() else float("nan")
    print(f"\n  ROC-AUC {auc:.3f}   PR-AUC {pr_auc:.3f}   (base rate {actual.mean():.3f})")

    clf = table[table.model == "classifier"].iloc[0]
    by_model = table.set_index("model").f1
    gains = {
        "majority-class": clf.f1 - by_model["majority-class"],
        "persistence-1lag": clf.f1 - by_model["persistence-1lag"],
        "persistence-2lag": clf.f1 - by_model["persistence-2lag"],
    }
    checks = {
        f"F1 beats majority by >= {MIN_F1_GAIN_OVER_MAJORITY:.2f}":
            gains["majority-class"] >= MIN_F1_GAIN_OVER_MAJORITY,
        f"F1 beats persistence-1lag by >= {MIN_F1_GAIN_OVER_HEURISTIC:.2f}":
            gains["persistence-1lag"] >= MIN_F1_GAIN_OVER_HEURISTIC,
        f"F1 beats persistence-2lag by >= {MIN_F1_GAIN_OVER_HEURISTIC:.2f}":
            gains["persistence-2lag"] >= MIN_F1_GAIN_OVER_HEURISTIC,
        f"detects >= {MIN_TRUE_POSITIVES} true positives":
            int(clf.tp) >= MIN_TRUE_POSITIVES,
    }
    print("\n  SHIP CRITERION (all must hold):")
    for label, passed in checks.items():
        print(f"    [{'PASS' if passed else 'FAIL'}] {label}")
    print("    gains: " + "  ".join(f"vs {k} {v:+.3f}" for k, v in gains.items())
          + f"  | TP {int(clf.tp)}")
    ship = all(checks.values())
    print(f"\n  DECISION: {'SHIP' if ship else 'DO NOT SHIP'}")
    return {
        "table": table, "ship": ship, "auc": auc, "pr_auc": pr_auc,
        "features": features, "results": results, "gains": gains, "windows": windows,
    }


if __name__ == "__main__":
    main()
