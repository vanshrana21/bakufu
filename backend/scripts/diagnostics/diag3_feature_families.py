"""
DIAGNOSTIC 3 - which family of features is the model actually using?

Sums XGBoost gain importance over four families and reports percentages.
Reads the trained bundle; changes nothing.

Run: python -m scripts.diagnostics.diag3_feature_families
"""

from __future__ import annotations

import argparse
import json

import joblib
import pandas as pd

from src.config.settings import settings
from src.data.preprocess.compute_indices import INDEX_COLUMNS
from src.models.prospectivity.enrich_features import AE_COLUMNS
from src.models.prospectivity.pu_xgboost import MODEL_PATH

RAW_BANDS = ["b02", "b03", "b04", "b08", "b11", "b12"]
DEM_FEATURES = ["elevation", "slope", "aspect"]


def family_of(name: str) -> str:
    if name in RAW_BANDS:
        return "raw_spectral_bands"
    if name in DEM_FEATURES:
        return "dem_derived"
    if name in INDEX_COLUMNS:
        return "spectral_indices"
    if name in AE_COLUMNS:
        return "autoencoder"
    return "other"


def main(model_path=MODEL_PATH, out_name="diag3_feature_families.json") -> None:
    bundle = joblib.load(model_path)
    model, features = bundle["model"], bundle["features"]

    importance = pd.Series(model.feature_importances_, index=features, dtype="float64")
    total = float(importance.sum())

    frame = pd.DataFrame({"importance": importance})
    frame["family"] = [family_of(f) for f in frame.index]
    sums = frame.groupby("family").importance.sum().sort_values(ascending=False)
    pct = (sums / total * 100.0) if total > 0 else sums * 0.0
    counts = frame.family.value_counts()

    print("=" * 60)
    print("DIAGNOSTIC 3 - FEATURE FAMILY IMPORTANCE")
    print("=" * 60)
    print("family".ljust(22) + "n".rjust(4) + "sum".rjust(11) + "pct".rjust(9))
    print("-" * 60)
    for family in sums.index:
        print(family.ljust(22) + str(counts[family]).rjust(4) + f"{sums[family]:>11.5f}" + f"{pct[family]:>8.2f}%")

    dominant = sums.index[0]
    dominant_pct = float(pct.iloc[0])
    healthy = dominant_pct <= 60.0
    print(f"\n  dominant family : {dominant} at {dominant_pct:.2f}%")
    print(f"  healthy (<=60%) : {healthy}")

    if dominant == "autoencoder" and dominant_pct >= 80.0:
        rec = "AE dominates - spectral indices are largely wasted; prune them in Phase 3."
    elif dominant == "dem_derived" and dominant_pct >= 60.0:
        rec = ("DEM dominates - model is learning terrain association rather than "
               "spectral mineralogy; weaker prospectivity signal.")
    elif dominant == "spectral_indices":
        rec = "Spectral indices lead - the ideal case; model learned real mineralogy."
    elif healthy:
        rec = "Balanced across families - keep all four, no pruning needed."
    else:
        rec = f"{dominant} dominates at {dominant_pct:.1f}% - rebalance in Phase 3."
    print(f"  recommendation  : {rec}")

    print("\n  Top 15 individual features:")
    for name, value in importance.sort_values(ascending=False).head(15).items():
        print("    " + str(name).ljust(24) + f"{value:.5f}  [{family_of(str(name))}]")

    out = settings.DATA_PROCESSED / out_name
    out.write_text(
        json.dumps(
            {
                "family_sums": sums.to_dict(),
                "family_pct": pct.to_dict(),
                "family_counts": counts.to_dict(),
                "dominant": dominant,
                "dominant_pct": dominant_pct,
                "healthy": bool(healthy),
                "recommendation": rec,
                "top15": importance.sort_values(ascending=False).head(15).to_dict(),
            },
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    print(f"  written to      : {out}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default=str(MODEL_PATH))
    parser.add_argument("--output", default="diag3_feature_families.json")
    a = parser.parse_args()
    main(a.model, a.output)
