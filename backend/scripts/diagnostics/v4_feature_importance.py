"""
Feature-importance breakdown for a trained prospectivity bundle.

Groups XGBoost gain importance into four families and reports the top 25
individual features plus family percentages, so a family that dominates for
the wrong reason (terrain standing in for "which raster did this come from")
is visible at a glance.

Run: python -m scripts.diagnostics.v4_feature_importance [--model v4|v5|<path>]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import joblib
import pandas as pd

from src.config.settings import settings

RAW_BANDS = ["b02", "b03", "b04", "b08", "b11", "b12"]
SPECTRAL_INDICES = [
    "mn_ratio_swir", "iron_ratio", "ferrous_ratio", "ndvi", "normalised_burn_ratio_swir",
]
TERRAIN = ["elevation", "slope", "aspect"]

#: Above this share, a single family is doing suspiciously much of the work.
TERRAIN_CONCERN_PCT: float = 25.0


def family_of(name: str) -> str:
    if name in RAW_BANDS:
        return "raw_bands"
    if name in SPECTRAL_INDICES:
        return "spectral_indices"
    if name in TERRAIN:
        return "terrain"
    if name.startswith("ae_"):
        return "autoencoder"
    return "other"


def resolve_model(value: str) -> Path:
    """Accept a version tag ('v4') or an explicit path."""
    candidate = Path(value)
    if candidate.exists():
        return candidate
    return settings.MODELS_DIR / f"prospectivity_{value}.pkl"


def analyse(model_path: Path, out_name: str | None = None) -> dict[str, object]:
    bundle = joblib.load(model_path)
    model, features = bundle["model"], bundle["features"]

    importance = pd.Series(model.feature_importances_, index=features, dtype="float64")
    total = float(importance.sum())

    frame = pd.DataFrame({"importance": importance})
    frame["family"] = [family_of(str(f)) for f in frame.index]
    sums = frame.groupby("family").importance.sum().sort_values(ascending=False)
    counts = frame.family.value_counts()
    pct = (sums / total * 100.0) if total > 0 else sums * 0.0

    print("=" * 66)
    print(f"FEATURE IMPORTANCE - {model_path.name}")
    print("=" * 66)
    print("family".ljust(20) + "n".rjust(5) + "sum".rjust(12) + "pct".rjust(10))
    print("-" * 66)
    for family in sums.index:
        print(
            str(family).ljust(20)
            + str(counts[family]).rjust(5)
            + f"{sums[family]:>12.5f}"
            + f"{pct[family]:>9.2f}%"
        )

    terrain_pct = float(pct.get("terrain", 0.0))
    print("")
    print(f"  terrain family    : {terrain_pct:.2f}%  (concern threshold {TERRAIN_CONCERN_PCT}%)")
    print(f"  terrain flagged   : {terrain_pct > TERRAIN_CONCERN_PCT}")
    print(f"  dominant family   : {sums.index[0]} at {float(pct.iloc[0]):.2f}%")

    print("")
    print("  Top 25 individual features:")
    ranked = importance.sort_values(ascending=False).head(25)
    for rank, (name, value) in enumerate(ranked.items(), start=1):
        print(f"    {rank:>2}. {str(name):<26} {value:.5f}  [{family_of(str(name))}]")

    payload = {
        "model": str(model_path),
        "family_sums": {k: float(v) for k, v in sums.items()},
        "family_pct": {k: float(v) for k, v in pct.items()},
        "family_counts": {k: int(v) for k, v in counts.items()},
        "terrain_pct": terrain_pct,
        "terrain_flagged": bool(terrain_pct > TERRAIN_CONCERN_PCT),
        "top25": {str(k): float(v) for k, v in ranked.items()},
        "n_train": bundle.get("n_train"),
        "n_positive": bundle.get("n_positive"),
        "elkan_noto_c": bundle.get("elkan_noto_c"),
    }
    out = settings.DATA_PROCESSED / (out_name or f"{model_path.stem}_feature_importance.json")
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print("")
    print(f"  written to        : {out}")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="v4", help="Version tag (v4, v5) or path to a .pkl")
    parser.add_argument("--output", default=None, help="Output JSON filename")
    args = parser.parse_args()
    analyse(resolve_model(args.model), args.output)


if __name__ == "__main__":
    main()
