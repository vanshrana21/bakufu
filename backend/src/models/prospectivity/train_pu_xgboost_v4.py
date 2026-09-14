"""Phase 2.8 - train the PU model with NGDR national records as positives.

Positive set grows from ~424 to ~1000 by adding NGDR records, weighted by how
precisely each is located. Validation adds a fifth fold holding out only NGDR
points far from every named block, which is the honest generalisation test:
nothing in that fold is near anything the model trained on.

Architecture and hyperparameters are unchanged from v3.

Run: python -m src.models.prospectivity.train_pu_xgboost_v4
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
from xgboost import XGBClassifier

from src.config.settings import settings
from src.data.preprocess.compute_indices import add_indices
from src.data.preprocess.extract_features import extract_features_bulk
from src.models.prospectivity.autoencoder import MODEL_PATH as AE_V1_PATH
from src.models.prospectivity.autoencoder import load_autoencoder
from src.models.prospectivity.enrich_features import AE_COLUMNS, embed_points
from src.models.prospectivity.pu_xgboost import (
    ALL_FEATURES,
    BASE_FEATURES,
    FOREIGN_WEIGHT,
    MAX_UNLABELLED_CANDIDATES_V3,
    PRIOR_TYPE_WEIGHTS,
    RANDOM_SEED,
    UNLABELLED_WEIGHT,
    XGB_PARAMS,
    XRF_WEIGHT,
    Dataset,
    _boreholes_with_priors,
    _surface_samples,
    sample_unlabelled,
)
from src.models.prospectivity.train_pu_xgboost import (
    MLFLOW_URI,
    TOP_K,
    estimate_label_frequency,
    top_k_precision,
)

EXPERIMENT: str = "phase_2_8_ngdr_expansion"

SAUSAR_V2: Path = settings.DATA_RAW / "satellite" / "s2_sausar_v2.tif"
NGDR_FEATURES: Path = settings.DATA_PROCESSED / "ngdr_features_v5.parquet"
FOREIGN_FEATURES: Path = settings.DATA_PROCESSED / "foreign_features_v3.parquet"
MODEL_PATH_V4: Path = settings.MODELS_DIR / "prospectivity_v4.pkl"

N_UNLABELLED_V4: int = 1500
EXCLUSION_M: float = 15000.0

#: Sentinel for absent terrain. Trees split on it as its own branch.
FILL_VALUES: dict[str, float] = {"elevation": -999.0, "slope": -999.0, "aspect": -999.0}

#: NGDR within this distance of a block joins that block's fold.
NEAR_BLOCK_KM: float = 50.0
#: NGDR beyond this distance from every block forms the generalisation fold.
FAR_BLOCK_KM: float = 100.0

V1_MEAN_AUC: float = 0.5902
V2_MEAN_AUC: float = 0.5552
V3_MEAN_AUC: float = 0.6466


def haversine_km(lat1, lon1, lat2, lon2) -> np.ndarray:
    """Great-circle distance in km between arrays of points."""
    radius = 6371.0
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dphi = p2 - p1
    dlambda = np.radians(lon2) - np.radians(lon1)
    a = np.sin(dphi / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dlambda / 2) ** 2
    return 2 * radius * np.arcsin(np.sqrt(a))


def build_dataset_v4(seed: int = RANDOM_SEED, verbose: bool = True) -> tuple[Dataset, pd.DataFrame]:
    """Assemble boreholes + XRF + foreign + NGDR positives and pseudo-negatives."""
    model = load_autoencoder(AE_V1_PATH)

    boreholes = _boreholes_with_priors()
    boreholes["label"] = 1
    boreholes["weight"] = boreholes.prior_type.map(PRIOR_TYPE_WEIGHTS).fillna(0.4)
    boreholes["source"] = "borehole"

    samples = _surface_samples()
    samples["label"] = 1
    samples["weight"] = XRF_WEIGHT
    samples["source"] = "xrf_sample"
    samples["block_name"] = samples.get("block_name", "KATORI-JHIRIYA")

    ngdr = pd.read_parquet(NGDR_FEATURES)
    ngdr["label"] = 1
    ngdr["source"] = "ngdr"
    ngdr["block_name"] = None

    foreign = pd.read_parquet(FOREIGN_FEATURES)
    foreign["label"] = 1
    foreign["weight"] = FOREIGN_WEIGHT
    foreign["source"] = "foreign"
    foreign["block_name"] = None

    # Every positive inside the Sausar raster pushes the negative sampler away,
    # so NGDR records there widen the exclusion zone alongside the boreholes.
    in_sausar = ngdr[ngdr.tile == "__sausar__"] if "tile" in ngdr.columns else ngdr.iloc[:0]
    exclusion_points = pd.concat(
        [boreholes[["lat", "lon"]], samples[["lat", "lon"]], in_sausar[["lat", "lon"]]],
        ignore_index=True,
    )

    positive_reference = add_indices(
        extract_features_bulk(exclusion_points[["lon", "lat"]], s2_path=SAUSAR_V2)
    )

    unlabelled = sample_unlabelled(
        exclusion_points,
        n=N_UNLABELLED_V4,
        seed=seed,
        s2_path=SAUSAR_V2,
        exclusion_m=EXCLUSION_M,
        max_candidates=MAX_UNLABELLED_CANDIDATES_V3,
        positives=positive_reference,
        reject_similar=True,
    )
    unlabelled["label"] = 0
    unlabelled["weight"] = UNLABELLED_WEIGHT
    unlabelled["source"] = "unlabelled"
    unlabelled["block_name"] = None

    # Boreholes, XRF and negatives are featurised against the Sausar mosaic;
    # NGDR and foreign arrive pre-featurised from their own tiles.
    live = pd.concat(
        [
            boreholes[["lat", "lon", "label", "weight", "source", "block_name"]],
            samples[["lat", "lon", "label", "weight", "source", "block_name"]],
            unlabelled[["lat", "lon", "label", "weight", "source", "block_name"]],
        ],
        ignore_index=True,
    )
    live = add_indices(extract_features_bulk(live, s2_path=SAUSAR_V2))
    live = pd.concat([live, embed_points(live, model, raster_path=SAUSAR_V2)], axis=1)

    columns = ["lat", "lon", "label", "weight", "source", "block_name"] + ALL_FEATURES
    combined = pd.concat(
        [
            live.reindex(columns=columns),
            ngdr.reindex(columns=columns),
            foreign.reindex(columns=columns),
        ],
        ignore_index=True,
    )

    combined[ALL_FEATURES] = combined[ALL_FEATURES].apply(pd.to_numeric, errors="coerce").astype("float64")
    usable = combined[AE_COLUMNS].notna().all(axis=1)
    combined = combined[usable].reset_index(drop=True)

    for column, value in FILL_VALUES.items():
        if column in combined.columns:
            combined[column] = combined[column].fillna(value)

    if verbose:
        counts = combined.groupby("source").size()
        print("=" * 68)
        print("PU DATASET v4")
        print("=" * 68)
        print(f"  Positives (boreholes)        : {int(counts.get('borehole', 0))}")
        print(f"  Positives (XRF)              : {int(counts.get('xrf_sample', 0))}")
        print(f"  Positives (foreign)          : {int(counts.get('foreign', 0))}")
        print(f"  Positives (NGDR)             : {int(counts.get('ngdr', 0))}")
        print(f"  Pseudo-negatives (validated) : {int(counts.get('unlabelled', 0))}")
        print(f"  Total training rows          : {len(combined)}")
        ngdr_rows = combined[combined.source == "ngdr"]
        if len(ngdr_rows):
            print("  NGDR by weight tier:")
            for weight, count in sorted(ngdr_rows.weight.value_counts().items()):
                print(f"    {weight:.1f} : {count}")

    return Dataset(frame=combined), boreholes


def assign_folds_v4(frame: pd.DataFrame, boreholes: pd.DataFrame, seed: int = RANDOM_SEED) -> tuple[np.ndarray, list[str]]:
    """Five folds: four block folds plus a far-NGDR generalisation fold."""
    rng = np.random.default_rng(seed)
    blocks = sorted(boreholes.block_name.dropna().unique())
    centroids = {
        block: (
            float(boreholes.loc[boreholes.block_name == block, "lat"].mean()),
            float(boreholes.loc[boreholes.block_name == block, "lon"].mean()),
        )
        for block in blocks
    }
    fold_names = list(blocks) + ["NGDR_FAR_GENERALISATION"]
    far_index = len(blocks)

    folds = np.full(len(frame), -1, dtype=int)
    block_to_fold = {block: i for i, block in enumerate(blocks)}

    lat = frame["lat"].to_numpy(dtype="float64")
    lon = frame["lon"].to_numpy(dtype="float64")
    distances = np.full((len(frame), len(blocks)), np.inf)
    for i, block in enumerate(blocks):
        blat, blon = centroids[block]
        distances[:, i] = haversine_km(lat, lon, blat, blon)
    nearest = distances.min(axis=1)
    nearest_block = distances.argmin(axis=1)

    for i, (source, block) in enumerate(zip(frame.source, frame.block_name, strict=True)):
        if source in ("borehole", "xrf_sample"):
            folds[i] = block_to_fold.get(block, -1)
        elif source == "ngdr":
            if nearest[i] <= NEAR_BLOCK_KM:
                folds[i] = int(nearest_block[i])
            elif nearest[i] > FAR_BLOCK_KM:
                folds[i] = far_index
            # 50-100 km: ambiguous, so train-only rather than contaminating a fold.
        elif source == "unlabelled":
            folds[i] = int(rng.integers(0, len(fold_names)))
        # foreign stays -1: training only.

    return folds, fold_names


def run_cv(dataset: Dataset, folds: np.ndarray, fold_names: list[str], log_mlflow: bool = True) -> pd.DataFrame:
    frame = dataset.frame
    X, y, w = dataset.X, dataset.y, dataset.w
    rows: list[dict[str, object]] = []

    for fold_index, name in enumerate(fold_names):
        test_mask = folds == fold_index
        train_mask = ~test_mask
        y_test = y[test_mask]
        if len(np.unique(y_test)) < 2:
            print(f"  [skip] fold {name}: test set has one class only")
            continue

        model = XGBClassifier(**XGB_PARAMS)
        model.fit(X[train_mask], y[train_mask], sample_weight=w[train_mask], verbose=False)
        scores = model.predict_proba(X[test_mask])[:, 1]

        base = float(y_test.mean())
        auc_pr = float(average_precision_score(y_test, scores))
        metrics: dict[str, object] = {
            "fold": name,
            "n_train": int(train_mask.sum()),
            "n_test": int(test_mask.sum()),
            "n_test_pos": int(y_test.sum()),
            "base_rate": base,
            "auc": float(roc_auc_score(y_test, scores)),
            "auc_pr": auc_pr,
            "lift": auc_pr / base if base > 0 else float("nan"),
        }
        for k in TOP_K:
            metrics[f"prec_at_{k}"] = top_k_precision(y_test, scores, k)
        rows.append(metrics)

        print(
            f"  fold {name:<26} n_train={metrics['n_train']:>5} n_test={metrics['n_test']:>4} "
            f"(pos {metrics['n_test_pos']:>3})  AUC={metrics['auc']:.3f}  "
            f"AUC-PR={auc_pr:.3f}  lift={metrics['lift']:.2f}x"
        )

        if log_mlflow:
            with mlflow.start_run(run_name=f"v4_fold_{name}"):
                mlflow.log_params({**XGB_PARAMS, "held_out": name, "n_features": len(ALL_FEATURES)})
                mlflow.log_metrics(
                    {k: v for k, v in metrics.items() if isinstance(v, (int, float)) and v is not None}
                )

    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default=str(MODEL_PATH_V4))
    args = parser.parse_args()

    for required in (NGDR_FEATURES, FOREIGN_FEATURES, SAUSAR_V2):
        if not Path(required).exists():
            raise FileNotFoundError(f"Phase 2.8 input missing: {required}")

    mlflow.set_tracking_uri(MLFLOW_URI)
    mlflow.set_experiment(EXPERIMENT)

    dataset, boreholes = build_dataset_v4()
    folds, fold_names = assign_folds_v4(dataset.frame, boreholes)

    print("")
    print("  fold membership:")
    for i, name in enumerate(fold_names):
        subset = dataset.frame[folds == i]
        by_source = ", ".join(f"{s}={n}" for s, n in subset.source.value_counts().items())
        print(f"    {name:<26} n={len(subset):>5}  ({by_source})")
    print(f"    {'(training only)':<26} n={int((folds == -1).sum()):>5}")

    print("")
    print("=" * 68)
    print("HYBRID LEAVE-OUT CV (5 folds)")
    print("=" * 68)
    results = run_cv(dataset, folds, fold_names)

    print("")
    print("=" * 68)
    print("FINAL MODEL")
    print("=" * 68)
    X, y, w = dataset.X, dataset.y, dataset.w
    final_model = XGBClassifier(**XGB_PARAMS)
    final_model.fit(X, y, sample_weight=w, verbose=False)
    c = estimate_label_frequency(X, y, w)
    importance = pd.Series(final_model.feature_importances_, index=dataset.features).sort_values(ascending=False)

    bundle = {
        "model": final_model,
        "features": dataset.features,
        "elkan_noto_c": c,
        "n_train": int(len(y)),
        "n_positive": int(y.sum()),
        "params": XGB_PARAMS,
        "fill_values": FILL_VALUES,
    }
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(bundle, out_path)

    print("")
    print("Per-fold results:")
    print(results.to_string(index=False))

    if not results.empty:
        mean_auc = float(results.auc.mean())
        mean_pr = float(results.auc_pr.mean())
        print("")
        print(f"  mean AUC (5 folds) : {mean_auc:.4f}")
        print(f"  mean AUC-PR        : {mean_pr:.4f}")
        print(f"  mean lift          : {results.lift.mean():.2f}x")
        for k in TOP_K:
            column = f"prec_at_{k}"
            if results[column].notna().any():
                print(f"  mean P@{k:<3d}         : {results[column].mean(skipna=True):.4f}")

        far = results[results.fold == "NGDR_FAR_GENERALISATION"]
        if not far.empty:
            print("")
            print(f"  >>> FOLD 5 (NGDR generalisation) AUC : {float(far.auc.iloc[0]):.4f}")
            print(f"  >>> FOLD 5 AUC-PR                    : {float(far.auc_pr.iloc[0]):.4f}")

        print("")
        print(f"  delta vs v1 (0.5902) : {mean_auc - V1_MEAN_AUC:+.4f}")
        print(f"  delta vs v2 (0.5552) : {mean_auc - V2_MEAN_AUC:+.4f}")
        print(f"  delta vs v3 (0.6466) : {mean_auc - V3_MEAN_AUC:+.4f}")

        with mlflow.start_run(run_name="prospectivity_v4_final"):
            mlflow.log_params({**XGB_PARAMS, "n_features": len(dataset.features)})
            mlflow.log_metrics(
                {
                    "mean_auc": mean_auc,
                    "mean_auc_pr": mean_pr,
                    "elkan_noto_c": c,
                    "n_train": len(y),
                    "n_positive": int(y.sum()),
                }
            )
            mlflow.log_dict(importance.head(30).to_dict(), "feature_importance.json")
            mlflow.log_artifact(str(out_path))

    print("")
    print("Top 20 features by gain:")
    for name, value in importance.head(20).items():
        print(f"  {name:<28s} {value:.5f}")

    print("")
    print(f"  Elkan-Noto c : {c:.4f}")
    print(f"  model saved  : {out_path}")

    metrics_path = settings.DATA_PROCESSED / "lobo_results_v4.json"
    metrics_path.write_text(json.dumps(results.to_dict(orient="records"), indent=2), encoding="utf-8")
    print(f"  fold metrics : {metrics_path}")


if __name__ == "__main__":
    main()
