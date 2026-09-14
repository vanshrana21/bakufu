"""Phase 2.7 - train the PU model with all three regularisation levers.

  Lever 1  domain-adversarial autoencoder embeddings (country-invariant)
  Lever 2  pseudo-negatives rejection-sampled against the positive class
  Lever 3  15 km borehole exclusion instead of 5 km

Architecture, hyperparameters and LOBO folds are unchanged from v2; only the
inputs and the negative-sampling policy differ. v1 and v2 artefacts are left
untouched - this writes prospectivity_v3.pkl.

Run: python -m src.models.prospectivity.train_pu_xgboost_v3
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import mlflow
import numpy as np
import pandas as pd

from src.config.settings import settings
from src.models.prospectivity.autoencoder import load_autoencoder
from src.models.prospectivity.pu_xgboost import (
    EXCLUSION_RADIUS_V3_M,
    MAX_UNLABELLED_CANDIDATES_V3,
    build_dataset,
)
from src.models.prospectivity.train_pu_xgboost import (
    MLFLOW_URI,
    TOP_K,
    run_lobo_cv,
    train_final,
)

EXPERIMENT: str = "phase_2_7_all_levers"

ADVERSARIAL_AE: Path = settings.MODELS_DIR / "autoencoder_v2_adversarial.pt"
FALLBACK_AE: Path = settings.MODELS_DIR / "autoencoder_v1.pt"
SAUSAR_V2: Path = settings.DATA_RAW / "satellite" / "s2_sausar_v2.tif"
FOREIGN_V4: Path = settings.DATA_PROCESSED / "foreign_features_v4.parquet"
FOREIGN_V3: Path = settings.DATA_PROCESSED / "foreign_features_v3.parquet"
MODEL_PATH_V3: Path = settings.MODELS_DIR / "prospectivity_v3.pkl"

#: Phase baselines, for reporting deltas.
V1_MEAN_AUC: float = 0.5902
V2_MEAN_AUC: float = 0.5552
V1_MEAN_AUC_PR: float = 0.0667
V2_MEAN_AUC_PR: float = 0.1332


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--ae",
        default=None,
        help="Autoencoder checkpoint (default: adversarial if present, else v1)",
    )
    parser.add_argument(
        "--foreign",
        default=None,
        help="Foreign features parquet (default: v4 if present, else v3)",
    )
    parser.add_argument("--buffer-m", type=float, default=EXCLUSION_RADIUS_V3_M)
    parser.add_argument(
        "--no-reject-similar",
        action="store_true",
        help="Disable Lever 2 (ablation).",
    )
    args = parser.parse_args()

    ae_path = Path(args.ae) if args.ae else (ADVERSARIAL_AE if ADVERSARIAL_AE.exists() else FALLBACK_AE)
    foreign_path = Path(args.foreign) if args.foreign else (FOREIGN_V4 if FOREIGN_V4.exists() else FOREIGN_V3)
    reject_similar = not args.no_reject_similar

    print("=" * 64)
    print("PHASE 2.7 - ALL LEVERS")
    print("=" * 64)
    print(f"  Lever 1 autoencoder : {ae_path.name}")
    print(f"  Lever 2 reject-similar: {reject_similar}")
    print(f"  Lever 3 buffer       : {args.buffer_m / 1000:.0f} km")
    print(f"  foreign features     : {foreign_path.name}")
    print(f"  raster               : {SAUSAR_V2.name}")

    for required in (ae_path, foreign_path, SAUSAR_V2):
        if not Path(required).exists():
            raise FileNotFoundError(f"Phase 2.7 input missing: {required}")

    mlflow.set_tracking_uri(MLFLOW_URI)
    mlflow.set_experiment(EXPERIMENT)

    autoencoder = load_autoencoder(ae_path)
    dataset = build_dataset(
        model=autoencoder,
        s2_path=SAUSAR_V2,
        foreign_features_path=foreign_path,
        exclusion_m=args.buffer_m,
        max_candidates=MAX_UNLABELLED_CANDIDATES_V3,
        reject_similar=reject_similar,
    )

    print("")
    print("=" * 64)
    print("LEAVE-ONE-BLOCK-OUT CV")
    print("=" * 64)
    results = run_lobo_cv(dataset)

    print("")
    print("=" * 64)
    print("FINAL MODEL")
    print("=" * 64)
    final = train_final(dataset, save_path=MODEL_PATH_V3)

    print("")
    print("Per-fold results:")
    print(results.to_string(index=False))

    if not results.empty:
        base_rates = results.n_test_pos / results.n_test
        lifts = results.auc_pr / base_rates
        print("")
        print("Per-fold lift over chance:")
        for fold, base, auc_pr, lift in zip(
            results.fold, base_rates, results.auc_pr, lifts, strict=True
        ):
            print(f"  {fold:<22} base={base:.4f}  AUC-PR={auc_pr:.4f}  lift={lift:.2f}x")

        mean_auc = float(results.auc.mean())
        mean_pr = float(results.auc_pr.mean())
        print("")
        print(f"  mean AUC     : {mean_auc:.4f}")
        print(f"  mean AUC-PR  : {mean_pr:.4f}")
        print(f"  mean lift    : {mean_pr / float(base_rates.mean()):.2f}x")
        for k in TOP_K:
            column = f"prec_at_{k}"
            if results[column].notna().any():
                print(f"  mean P@{k:<3d}  : {results[column].mean(skipna=True):.4f}")

        print("")
        print(f"  delta vs v1 (AUC {V1_MEAN_AUC:.4f}) : {mean_auc - V1_MEAN_AUC:+.4f}")
        print(f"  delta vs v2 (AUC {V2_MEAN_AUC:.4f}) : {mean_auc - V2_MEAN_AUC:+.4f}")
        print(f"  delta vs v1 (AUC-PR {V1_MEAN_AUC_PR:.4f}) : {mean_pr - V1_MEAN_AUC_PR:+.4f}")
        print(f"  delta vs v2 (AUC-PR {V2_MEAN_AUC_PR:.4f}) : {mean_pr - V2_MEAN_AUC_PR:+.4f}")

        if mean_auc >= 0.70:
            flag = "SHIP - prospectivity is demo-worthy"
        elif mean_auc >= 0.62:
            flag = "MEANINGFUL but not conclusive - ship with honest framing"
        elif mean_auc >= 0.60:
            flag = "CEILING HIT - ship as pipeline demonstrator"
        elif mean_auc < 0.58:
            flag = "REGRESSION - a lever backfired; do not ship a worse model"
        else:
            flag = "between thresholds"
        print(f"  decision flag: {flag}")

    print("")
    print("Top 15 features by gain:")
    for name, value in final["importance"].head(15).items():
        print(f"  {name:<28s} {value:.5f}")

    print("")
    print(f"  Elkan-Noto c : {final['c']:.4f}")
    print(f"  model saved  : {final['path']}")

    metrics_path = settings.DATA_PROCESSED / "lobo_results_v3.json"
    metrics_path.write_text(json.dumps(results.to_dict(orient="records"), indent=2), encoding="utf-8")
    print(f"  fold metrics : {metrics_path}")


if __name__ == "__main__":
    main()
