"""Phase 2.9 - train v5 on terrain-corrected, globally-sampled data.

Differences from v4:
  - every positive carries real Copernicus terrain, so the -999 sentinel that
    became a near-perfect positive indicator in v4 is gone
  - pseudo-negatives are drawn from Sausar, foreign and NGDR tiles alike rather
    than from Sausar only, removing the raster-provenance shortcut
  - NGDR positives come from multi-scene composited tiles where available

Architecture, hyperparameters and the 5-fold structure are unchanged from v4.
v1-v4 artefacts are untouched; this writes prospectivity_v5.pkl.

Run: python -m src.models.prospectivity.train_pu_xgboost_v5
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import mlflow
import numpy as np
import pandas as pd

from src.config.settings import settings
from src.data.preprocess.compute_indices import add_indices
from src.data.preprocess.extract_features import extract_features_bulk
from src.models.prospectivity.autoencoder import load_autoencoder
from src.models.prospectivity.enrich_features import AE_COLUMNS, embed_points
from src.models.prospectivity.pu_xgboost import (
    ALL_FEATURES,
    EXCLUSION_RADIUS_V3_M,
    PRIOR_TYPE_WEIGHTS,
    UNLABELLED_WEIGHT,
    XRF_WEIGHT,
    Dataset,
    _boreholes_with_priors,
    _surface_samples,
    sample_unlabelled_global,
)
from src.models.prospectivity.train_pu_xgboost import MLFLOW_URI, TOP_K, train_final
from src.models.prospectivity.train_pu_xgboost_v4 import assign_folds_v4, run_cv

EXPERIMENT: str = "phase_2_9_dem_expansion"

SAUSAR_V2: Path = settings.DATA_RAW / "satellite" / "s2_sausar_v2.tif"
AE_V1: Path = settings.MODELS_DIR / "autoencoder_v1.pt"
FOREIGN_V5: Path = settings.DATA_PROCESSED / "foreign_features_v5.parquet"
NGDR_V6: Path = settings.DATA_PROCESSED / "ngdr_features_v6.parquet"
MODEL_PATH_V5: Path = settings.MODELS_DIR / "prospectivity_v5.pkl"

FOREIGN_WEIGHT: float = 0.5

#: Measured Phase 2.8 baselines, read from the artefacts rather than the brief.
V4_MEAN_AUC: float = 0.9218
V4_FOLD5_AUC: float = 0.9982


def build_dataset_v5(
    foreign_path: Path = FOREIGN_V5,
    ngdr_path: Path = NGDR_V6,
    n_per_region: int = 500,
    reject_similar: bool = True,
    verbose: bool = True,
) -> tuple[Dataset, pd.DataFrame]:
    """Assemble positives from every source plus globally-sampled negatives."""
    autoencoder = load_autoencoder(AE_V1)

    boreholes = _boreholes_with_priors()
    boreholes["label"] = 1
    boreholes["weight"] = boreholes.prior_type.map(PRIOR_TYPE_WEIGHTS).fillna(0.4)
    boreholes["source"] = "borehole"

    samples = _surface_samples()
    samples["label"] = 1
    samples["weight"] = XRF_WEIGHT
    samples["source"] = "xrf_sample"

    foreign = pd.read_parquet(foreign_path)
    foreign["label"] = 1
    foreign["weight"] = FOREIGN_WEIGHT
    foreign["source"] = "foreign"
    foreign["block_name"] = None

    ngdr = pd.read_parquet(ngdr_path)
    ngdr["label"] = 1
    ngdr["source"] = "ngdr"
    ngdr["block_name"] = None
    if "weight" not in ngdr.columns:
        ngdr["weight"] = 0.6

    # Every positive contributes to the exclusion buffer, not just boreholes.
    all_positives = pd.concat(
        [f[["lon", "lat"]] for f in (boreholes, samples, foreign, ngdr)], ignore_index=True
    )

    positive_reference = add_indices(
        extract_features_bulk(boreholes[["lon", "lat"]], s2_path=SAUSAR_V2)
    )

    unlabelled = sample_unlabelled_global(
        all_positives,
        n_per_region=n_per_region,
        exclusion_m=EXCLUSION_RADIUS_V3_M,
        positives_reference=positive_reference,
        reject_similar=reject_similar,
        verbose=verbose,
    )
    unlabelled["label"] = 0
    unlabelled["weight"] = UNLABELLED_WEIGHT
    unlabelled["source"] = "unlabelled"
    unlabelled["block_name"] = None

    # Negatives are featurised per originating tile so each point is read from
    # the raster it was drawn from.
    negative_pieces: list[pd.DataFrame] = []
    tile_dir = settings.DATA_RAW / "satellite" / "unlabelled"
    for tile_name, group in unlabelled.groupby("tile"):
        raster = SAUSAR_V2 if str(tile_name) == SAUSAR_V2.name else tile_dir / str(tile_name)
        points = group[["lon", "lat"]].reset_index(drop=True)
        block = add_indices(extract_features_bulk(points, s2_path=raster))
        embeddings = embed_points(block, autoencoder, raster_path=raster)
        block = pd.concat([block, embeddings], axis=1)
        for column in ("label", "weight", "source", "block_name", "region"):
            block[column] = group[column].to_numpy()
        negative_pieces.append(block)
    negatives = pd.concat(negative_pieces, ignore_index=True)

    # Domestic positives are read from the Sausar mosaic.
    domestic = pd.concat([boreholes, samples], ignore_index=True)
    domestic_features = add_indices(
        extract_features_bulk(domestic[["lon", "lat"]], s2_path=SAUSAR_V2)
    )
    domestic_embeddings = embed_points(domestic_features, autoencoder, raster_path=SAUSAR_V2)
    domestic_full = pd.concat([domestic_features, domestic_embeddings], axis=1)
    for column in ("label", "weight", "source", "block_name"):
        domestic_full[column] = domestic[column].to_numpy()

    keep = ["lon", "lat", "label", "weight", "source", "block_name"] + list(ALL_FEATURES)

    def _align(frame: pd.DataFrame) -> pd.DataFrame:
        out = frame.reindex(columns=keep)
        return out

    combined = pd.concat(
        [_align(domestic_full), _align(foreign), _align(ngdr), _align(negatives)],
        ignore_index=True,
    )

    usable = combined[AE_COLUMNS].notna().all(axis=1)
    combined = combined[usable].reset_index(drop=True)
    combined[ALL_FEATURES] = combined[ALL_FEATURES].apply(pd.to_numeric, errors="coerce").astype("float64")

    if verbose:
        terrain = combined[["elevation", "slope", "aspect"]]
        missing_terrain = terrain.isna().all(axis=1)
        print("")
        print("=" * 64)
        print("PU DATASET v5")
        print("=" * 64)
        for source, group in combined.groupby("source"):
            print(f"  {source:<12} n={len(group):>5}  label={int(group.label.iloc[0])}  "
                  f"mean weight={group.weight.mean():.2f}")
        print(f"  total rows   : {len(combined)}")
        print(f"  feature NaNs : {int(combined[ALL_FEATURES].isna().sum().sum())}")
        print("")
        print("  terrain-missing leak check:")
        print(f"    rows without terrain      : {int(missing_terrain.sum())}")
        if missing_terrain.any():
            print(f"    P(label=1 | terrain NaN)  : {combined.loc[missing_terrain,'label'].mean():.4f}")
        print(f"    P(label=1 | terrain real) : {combined.loc[~missing_terrain,'label'].mean():.4f}")

    return Dataset(frame=combined), boreholes


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--foreign", default=str(FOREIGN_V5))
    parser.add_argument("--ngdr", default=str(NGDR_V6))
    parser.add_argument("--per-region", type=int, default=500)
    parser.add_argument(
        "--no-reject-similar",
        action="store_true",
        help="Disable Lever 2 spectral/terrain rejection. Lever 2 defines negatives as "
             "points unlike positives on mn_ratio_swir, then the model separates the "
             "classes on mn_ratio_swir - circular, and the source of the inflated CV.",
    )
    parser.add_argument("--out-model", default=None, help="Model filename to write")
    parser.add_argument("--out-metrics", default=None, help="Fold-metrics filename")
    args = parser.parse_args()

    mlflow.set_tracking_uri(MLFLOW_URI)
    mlflow.set_experiment(EXPERIMENT)

    dataset, boreholes = build_dataset_v5(
        foreign_path=Path(args.foreign),
        ngdr_path=Path(args.ngdr),
        n_per_region=args.per_region,
        reject_similar=not args.no_reject_similar,
    )

    folds, fold_names = assign_folds_v4(dataset.frame, boreholes)

    print("")
    print("=" * 64)
    print("HYBRID LEAVE-OUT CV (5 folds)")
    print("=" * 64)
    results = run_cv(dataset, folds, fold_names)

    print("")
    print("=" * 64)
    print("FINAL MODEL")
    print("=" * 64)
    save_path = (settings.MODELS_DIR / args.out_model) if args.out_model else MODEL_PATH_V5
    final = train_final(dataset, save_path=save_path)

    print("")
    print(results.to_string(index=False))

    if not results.empty:
        base = results.n_test_pos / results.n_test
        lift = results.auc_pr / base
        print("")
        for fold, b, pr, lf in zip(results.fold, base, results.auc_pr, lift, strict=True):
            print(f"  {fold:<26} base={b:.4f}  AUC-PR={pr:.4f}  lift={lf:.2f}x")

        mean_auc = float(results.auc.mean())
        fold5 = results[results.fold.astype(str).str.startswith("NGDR_FAR")]
        fold5_auc = float(fold5.auc.iloc[0]) if len(fold5) else float("nan")

        print("")
        print(f"  mean AUC (5 folds) : {mean_auc:.4f}")
        print(f"  mean AUC-PR        : {float(results.auc_pr.mean()):.4f}")
        print(f"  mean lift          : {float(lift.mean()):.2f}x")
        for k in TOP_K:
            column = f"prec_at_{k}"
            if column in results and results[column].notna().any():
                print(f"  mean P@{k:<3d}         : {results[column].mean(skipna=True):.4f}")
        print("")
        print(f"  >>> FOLD 5 (NGDR generalisation) AUC : {fold5_auc:.4f}")
        print("")
        print(f"  delta vs v4 measured mean AUC ({V4_MEAN_AUC:.4f}) : {mean_auc - V4_MEAN_AUC:+.4f}")
        print(f"  delta vs v4 measured Fold 5   ({V4_FOLD5_AUC:.4f}) : {fold5_auc - V4_FOLD5_AUC:+.4f}")

    print("")
    print("Top 25 features by gain:")
    for name, value in final["importance"].head(25).items():
        print(f"  {name:<28s} {value:.5f}")

    print("")
    print(f"  Elkan-Noto c : {final['c']:.4f}")
    print(f"  model saved  : {final['path']}")

    metrics_path = settings.DATA_PROCESSED / (args.out_metrics or "lobo_results_v5.json")
    metrics_path.write_text(json.dumps(results.to_dict(orient="records"), indent=2), encoding="utf-8")
    print(f"  fold metrics : {metrics_path}")


if __name__ == "__main__":
    main()
