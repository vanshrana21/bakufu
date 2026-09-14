"""Train the PU prospectivity model with leave-one-block-out validation.

Run: python -m src.models.prospectivity.train_pu_xgboost
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import joblib
import mlflow
import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.model_selection import StratifiedKFold
from xgboost import XGBClassifier

from src.config.settings import settings
from src.models.prospectivity.pu_xgboost import (
    ALL_FEATURES,
    MODEL_PATH,
    RANDOM_SEED,
    XGB_PARAMS,
    Dataset,
    build_dataset,
)

MLFLOW_URI: str = (settings.PROJECT_ROOT / "mlruns").as_uri()
EXPERIMENT: str = "manganese-prospectivity"
TOP_K: tuple[int, ...] = (5, 10, 20)

#: Phase 2.5 inputs and output, kept separate so Phase 2 artefacts survive.
SAUSAR_V2_PATH: Path = settings.DATA_RAW / "satellite" / "s2_sausar_v2.tif"
FOREIGN_FEATURES_V3: Path = settings.DATA_PROCESSED / "foreign_features_v3.parquet"
MODEL_PATH_V2: Path = settings.MODELS_DIR / "prospectivity_v2.pkl"


def top_k_precision(y_true: np.ndarray, scores: np.ndarray, k: int) -> float | None:
    """Fraction of the k highest-scored items that are true positives."""
    if len(y_true) < k:
        return None
    order = np.argsort(scores)[::-1][:k]
    return float(np.mean(y_true[order]))


def estimate_label_frequency(
    X: pd.DataFrame,
    y: np.ndarray,
    w: np.ndarray,
    n_splits: int = 3,
    seed: int = RANDOM_SEED,
) -> float:
    """Elkan-Noto c = P(labelled | positive), from out-of-fold predictions.

    Estimated by cross-fitting so the positives used for the estimate were
    never seen in the fit that scores them.
    """
    positives = np.flatnonzero(y == 1)
    if len(positives) < n_splits * 2:
        return 1.0

    out_of_fold = np.full(len(y), np.nan)
    splitter = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=seed)
    for fit_index, score_index in splitter.split(X, y):
        model = XGBClassifier(**XGB_PARAMS)
        model.fit(X.iloc[fit_index], y[fit_index], sample_weight=w[fit_index], verbose=False)
        out_of_fold[score_index] = model.predict_proba(X.iloc[score_index])[:, 1]

    c = float(np.nanmean(out_of_fold[positives]))
    # Guard against a degenerate estimate making the adjustment explode.
    return float(np.clip(c, 1e-3, 1.0))


def _fold_assignment(frame: pd.DataFrame, blocks: list[str], seed: int = RANDOM_SEED) -> np.ndarray:
    """Assign every row to a LOBO fold.

    Positives go to their own block's fold. Unlabelled points carry no block,
    so they are spread evenly across folds to give each held-out block a test
    set with both classes. Foreign positives are training-only (fold -1).
    """
    rng = np.random.default_rng(seed)
    folds = np.full(len(frame), -1, dtype=int)

    block_to_fold = {block: i for i, block in enumerate(blocks)}
    for i, (block, source) in enumerate(zip(frame.block_name, frame.source, strict=True)):
        if source == "foreign":
            folds[i] = -1
        elif source == "unlabelled":
            folds[i] = rng.integers(0, len(blocks))
        elif block in block_to_fold:
            folds[i] = block_to_fold[block]
    return folds


def run_lobo_cv(dataset: Dataset, log_mlflow: bool = True) -> pd.DataFrame:
    """Leave-one-block-out cross-validation. Returns per-fold metrics."""
    frame = dataset.frame
    blocks = sorted(frame.loc[frame.source == "borehole", "block_name"].dropna().unique())
    folds = _fold_assignment(frame, blocks)
    frame = frame.assign(fold=folds)

    X, y, w = dataset.X, dataset.y, dataset.w
    rows: list[dict[str, object]] = []

    for fold_index, block in enumerate(blocks):
        test_mask = (frame.fold == fold_index).to_numpy()
        # Foreign positives (fold -1) always train; never test.
        train_mask = ~test_mask

        y_test = y[test_mask]
        if len(np.unique(y_test)) < 2:
            print(f"  [skip] fold {block}: test set has one class only")
            continue

        model = XGBClassifier(**XGB_PARAMS)
        model.fit(X[train_mask], y[train_mask], sample_weight=w[train_mask], verbose=False)
        scores = model.predict_proba(X[test_mask])[:, 1]

        c = estimate_label_frequency(X[train_mask], y[train_mask], w[train_mask])
        metrics: dict[str, object] = {
            "fold": block,
            "n_train": int(train_mask.sum()),
            "n_test": int(test_mask.sum()),
            "n_test_pos": int(y_test.sum()),
            "auc": float(roc_auc_score(y_test, scores)),
            "auc_pr": float(average_precision_score(y_test, scores)),
            "elkan_noto_c": c,
        }
        for k in TOP_K:
            metrics[f"prec_at_{k}"] = top_k_precision(y_test, scores, k)
        rows.append(metrics)

        print(
            f"  fold {block:<20s} n_train={metrics['n_train']:>5} "
            f"n_test={metrics['n_test']:>4} (pos {metrics['n_test_pos']:>3})  "
            f"AUC={metrics['auc']:.3f}  AUC-PR={metrics['auc_pr']:.3f}"
        )

        if log_mlflow:
            with mlflow.start_run(run_name=f"lobo_{block}"):
                mlflow.log_params({**XGB_PARAMS, "held_out_block": block, "n_features": len(ALL_FEATURES)})
                mlflow.log_metrics(
                    {k: v for k, v in metrics.items() if isinstance(v, (int, float)) and v is not None}
                )

    return pd.DataFrame(rows)


def train_final(dataset: Dataset, save_path: Path = MODEL_PATH, log_mlflow: bool = True) -> dict[str, object]:
    """Retrain on everything and persist the model bundle."""
    X, y, w = dataset.X, dataset.y, dataset.w
    model = XGBClassifier(**XGB_PARAMS)
    model.fit(X, y, sample_weight=w, verbose=False)

    c = estimate_label_frequency(X, y, w)
    importance = (
        pd.Series(model.feature_importances_, index=dataset.features)
        .sort_values(ascending=False)
    )

    bundle = {
        "model": model,
        "features": dataset.features,
        "elkan_noto_c": c,
        "n_train": int(len(y)),
        "n_positive": int(y.sum()),
        "params": XGB_PARAMS,
    }
    save_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(bundle, save_path)

    if log_mlflow:
        with mlflow.start_run(run_name="prospectivity_v1_final"):
            mlflow.log_params({**XGB_PARAMS, "n_features": len(dataset.features)})
            mlflow.log_metrics(
                {"elkan_noto_c": c, "n_train": len(y), "n_positive": int(y.sum())}
            )
            mlflow.log_dict(importance.head(30).to_dict(), "feature_importance.json")
            mlflow.log_artifact(str(save_path))

    return {"model": model, "c": c, "importance": importance, "path": save_path}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--version",
        default="v1",
        choices=("v1", "v2"),
        help="v1: Phase 2 baseline. v2: Phase 2.5 cleaner data (re-composed mosaic + cluster-tile foreign positives).",
    )
    args = parser.parse_args()
    is_v2 = args.version == "v2"

    experiment = "phase_2_5_cleaner_data" if is_v2 else EXPERIMENT
    mlflow.set_tracking_uri(MLFLOW_URI)
    mlflow.set_experiment(experiment)

    s2_path = SAUSAR_V2_PATH if is_v2 else None
    foreign_path = FOREIGN_FEATURES_V3 if is_v2 else None
    model_path = MODEL_PATH_V2 if is_v2 else MODEL_PATH

    if is_v2:
        for required in (s2_path, foreign_path):
            if not Path(required).exists():
                raise FileNotFoundError(f"Phase 2.5 input missing: {required}")
        print(f"Phase 2.5 run: raster={Path(s2_path).name}, foreign={Path(foreign_path).name}")

    dataset = build_dataset(s2_path=s2_path, foreign_features_path=foreign_path)

    print("\n" + "=" * 60)
    print("LEAVE-ONE-BLOCK-OUT CV")
    print("=" * 60)
    results = run_lobo_cv(dataset)

    print("\n" + "=" * 60)
    print("FINAL MODEL")
    print("=" * 60)
    final = train_final(dataset, save_path=model_path)

    print("\nPer-fold results:")
    print(results.to_string(index=False))

    if not results.empty:
        base_rates = results.n_test_pos / results.n_test
        lifts = results.auc_pr / base_rates
        print("\nPer-fold lift over chance:")
        for fold, base, auc_pr, lift in zip(results.fold, base_rates, results.auc_pr, lifts, strict=True):
            print(f"  {fold:<22} base={base:.4f}  AUC-PR={auc_pr:.4f}  lift={lift:.2f}x")

        print(f"\n  mean AUC     : {results.auc.mean():.4f}")
        print(f"  mean AUC-PR  : {results.auc_pr.mean():.4f}")
        print(f"  mean base    : {base_rates.mean():.4f}")
        print(f"  mean lift    : {results.auc_pr.mean() / base_rates.mean():.2f}x")
        for k in TOP_K:
            column = f"prec_at_{k}"
            if results[column].notna().any():
                print(f"  mean P@{k:<3d}  : {results[column].mean(skipna=True):.4f}")

        if is_v2:
            print(f"\n  delta vs Phase 2 v1 (mean AUC 0.5902): {results.auc.mean() - 0.5902:+.4f}")
            print(f"  delta vs Phase 2 v1 (mean AUC-PR 0.0667): {results.auc_pr.mean() - 0.0667:+.4f}")

    print("\nTop 15 features by gain:")
    for name, value in final["importance"].head(15).items():
        print(f"  {name:<28s} {value:.5f}")

    print(f"\n  Elkan-Noto c : {final['c']:.4f}")
    print(f"  model saved  : {final['path']}")

    suffix = "_v2" if is_v2 else ""
    metrics_path = settings.DATA_PROCESSED / f"lobo_results{suffix}.json"
    metrics_path.write_text(json.dumps(results.to_dict(orient="records"), indent=2), encoding="utf-8")
    print(f"  fold metrics : {metrics_path}")


if __name__ == "__main__":
    main()
