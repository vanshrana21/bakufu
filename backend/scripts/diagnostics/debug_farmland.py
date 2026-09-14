"""
Why does farmland north of Nagpur (21.55, 79.30) score 0.99 in v6?

Extracts the full 78-dim feature vector at the false positive and at two known
positives, ranks which features make them look alike, compares the farmland
values against the training positive distribution, and attributes the
prediction with SHAP - so the failure can be classified as spectral, terrain,
autoencoder, or compound confusion.

Read-only: loads v6, changes nothing.

Run: python -m scripts.diagnostics.debug_farmland
"""

from __future__ import annotations

import json
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import shap

from src.config.settings import settings
from src.data.preprocess.compute_indices import INDEX_COLUMNS, add_indices
from src.data.preprocess.extract_features import extract_features_bulk
from src.models.prospectivity.autoencoder import load_autoencoder
from src.models.prospectivity.enrich_features import AE_COLUMNS, embed_points
from src.models.prospectivity.explain import load_bundle

warnings.filterwarnings("ignore")

S2_PATH: Path = settings.DATA_RAW / "satellite" / "s2_sausar_v2.tif"
AE_PATH: Path = settings.MODELS_DIR / "autoencoder_v1.pt"
MODEL_PATH: Path = settings.MODELS_DIR / "prospectivity_v6.pkl"

#: v6 trained on these; training_set_v5.parquet was never produced.
FOREIGN_POSITIVES: Path = settings.DATA_PROCESSED / "foreign_features_v6.parquet"
NGDR_POSITIVES: Path = settings.DATA_PROCESSED / "ngdr_features_v7.parquet"

OUT_JSON: Path = settings.DATA_PROCESSED / "farmland_diagnostic.json"
OUT_MD: Path = settings.DATA_PROCESSED / "farmland_diagnostic.md"

BANDS = ["b02", "b03", "b04", "b08", "b11", "b12"]
TERRAIN = ["elevation", "slope", "aspect"]

POINTS: list[tuple[str, float, float]] = [
    ("Farmland", 21.55, 79.30),
    ("Ukwa", 21.71, 79.79),
    ("Katori", 21.58, 79.86),
]


def assemble(points: pd.DataFrame) -> pd.DataFrame:
    """The same feature path the v6 trainer used for Sausar points."""
    model = load_autoencoder(AE_PATH)
    frame = add_indices(extract_features_bulk(points, s2_path=S2_PATH))
    embeddings = embed_points(frame, model, raster_path=S2_PATH)
    return pd.concat([frame, embeddings], axis=1)


def main() -> None:
    bundle = load_bundle(MODEL_PATH)
    features: list[str] = list(bundle["features"])

    points = pd.DataFrame(
        [{"lon": lon, "lat": lat} for _, lat, lon in POINTS]
    )
    frame = assemble(points)
    frame.index = [name for name, _, _ in POINTS]

    X = frame.reindex(columns=features).astype("float64")
    for column, value in (bundle.get("fill_values") or {}).items():
        if column in X.columns:
            X[column] = X[column].fillna(value)

    booster = bundle["model"]
    margins = booster.predict(X, output_margin=True)
    raw = booster.predict_proba(X)[:, 1]
    c = float(bundle.get("elkan_noto_c") or 1.0)
    adjusted = np.clip(raw / max(c, 1e-6), 0.0, 0.99)

    # ---------- Step 1: feature table ----------
    print("=" * 74)
    print("STEP 1 - FEATURE COMPARISON")
    print("=" * 74)
    header = "Feature".ljust(30) + "Farmland".rjust(14) + "Ukwa".rjust(14) + "Katori".rjust(14)
    print(header)
    print("-" * 74)

    nan_notes: list[str] = []
    for name in BANDS + list(INDEX_COLUMNS) + TERRAIN:
        row = "  " + name.ljust(28)
        for label, _, _ in POINTS:
            value = frame.loc[label, name] if name in frame.columns else np.nan
            if pd.isna(value):
                row += "NaN".rjust(14)
                nan_notes.append(f"{name} at {label}")
            else:
                row += f"{float(value):>14.4f}"
        print(row)

    ae_norms: dict[str, float] = {}
    print("  " + "-" * 66)
    row = "  " + "AE embedding L2 norm".ljust(28)
    for label, _, _ in POINTS:
        vector = frame.loc[label, AE_COLUMNS].to_numpy(dtype="float64")
        norm = float(np.linalg.norm(vector))
        ae_norms[label] = norm
        row += f"{norm:>14.4f}"
    print(row)

    print("")
    print("  AE embedding, first 10 dims:")
    for i in range(10):
        column = AE_COLUMNS[i]
        row = "    " + column.ljust(26)
        for label, _, _ in POINTS:
            row += f"{float(frame.loc[label, column]):>14.4f}"
        print(row)

    print("")
    print("  " + "prediction".ljust(28) + "".join(f"{a:>14.4f}" for a in adjusted))
    print("  " + "raw margin".ljust(28) + "".join(f"{m:>14.4f}" for m in margins))

    # ---------- Step 2: similarity ranking ----------
    farmland = X.loc["Farmland"]
    ukwa = X.loc["Ukwa"]
    katori = X.loc["Katori"]

    # Scale each feature by the positive-class spread so ratios and elevations
    # are comparable; a raw metre-vs-ratio difference would be meaningless.
    positives = pd.concat(
        [pd.read_parquet(FOREIGN_POSITIVES), pd.read_parquet(NGDR_POSITIVES)],
        ignore_index=True,
    ).reindex(columns=features).astype("float64")
    scale = positives.std().replace(0.0, np.nan)

    diff = pd.DataFrame(
        {
            "vs_ukwa": (farmland - ukwa).abs(),
            "vs_katori": (farmland - katori).abs(),
        }
    )
    diff["avg_abs_diff"] = diff.mean(axis=1)
    diff["scaled"] = diff["avg_abs_diff"] / scale
    ranked = diff.sort_values("scaled")

    print("")
    print("=" * 74)
    print("STEP 2 - MOST SIMILAR / MOST DIFFERENT")
    print("=" * 74)
    print("  Top 15 MOST SIMILAR (farmland looks like the positives):")
    print("    " + "feature".ljust(26) + "avg|diff|".rjust(12) + "scaled".rjust(10))
    for name, row in ranked.head(15).iterrows():
        print(f"    {str(name):<26}{row.avg_abs_diff:>12.4f}{row.scaled:>10.4f}")

    print("")
    print("  Top 15 MOST DIFFERENT (should have flagged farmland):")
    print("    " + "feature".ljust(26) + "avg|diff|".rjust(12) + "scaled".rjust(10))
    for name, row in ranked.dropna(subset=["scaled"]).tail(15).iloc[::-1].iterrows():
        print(f"    {str(name):<26}{row.avg_abs_diff:>12.4f}{row.scaled:>10.4f}")

    # ---------- Step 3: percentile within positives ----------
    print("")
    print("=" * 74)
    print("STEP 3 - FARMLAND vs TRAINING POSITIVE DISTRIBUTION")
    print("=" * 74)
    percentiles: dict[str, float] = {}
    for name in features:
        column = positives[name].dropna()
        if column.empty:
            continue
        percentiles[name] = float((column < farmland[name]).mean() * 100.0)

    inside = {k: v for k, v in percentiles.items() if 25.0 <= v <= 75.0}
    ordered = sorted(inside.items(), key=lambda kv: abs(kv[1] - 50.0))
    print(f"  positives used : {len(positives)} (foreign v6 + NGDR v7)")
    print(f"  features inside the 25-75th percentile of positives: {len(inside)} / {len(percentiles)}")
    print("")
    print("  Top 10 closest to the positive median:")
    print("    " + "feature".ljust(26) + "pctile".rjust(9) + "farmland".rjust(13))
    for name, pct in ordered[:10]:
        print(f"    {name:<26}{pct:>9.1f}{farmland[name]:>13.4f}")

    # ---------- Step 4: SHAP ----------
    explainer = shap.TreeExplainer(booster)
    shap_values = explainer.shap_values(X)
    farmland_shap = pd.Series(shap_values[0], index=features)
    base_value = float(explainer.expected_value)

    positive_shap = farmland_shap[farmland_shap > 0].sort_values(ascending=False)
    negative_shap = farmland_shap[farmland_shap < 0].sort_values()

    print("")
    print("=" * 74)
    print("STEP 4 - SHAP ATTRIBUTION AT FARMLAND")
    print("=" * 74)
    print(f"  base value (margin)      : {base_value:.5f}")
    print(f"  farmland margin          : {float(margins[0]):.5f}")
    print(f"  farmland raw probability : {float(raw[0]):.6f}")
    print(f"  farmland adjusted (cap)  : {float(adjusted[0]):.4f}")
    print(f"  sum positive SHAP        : {float(positive_shap.sum()):+.5f}")
    print(f"  sum negative SHAP        : {float(negative_shap.sum()):+.5f}")
    print(f"  net                      : {float(farmland_shap.sum()):+.5f}")

    print("")
    print("  Top 10 pushing UP:")
    print("    " + "feature".ljust(26) + "shap".rjust(11) + "value".rjust(13))
    for name, value in positive_shap.head(10).items():
        print(f"    {str(name):<26}{value:>+11.5f}{farmland[name]:>13.4f}")

    print("")
    print("  Top 10 pushing DOWN:")
    print("    " + "feature".ljust(26) + "shap".rjust(11) + "value".rjust(13))
    for name, value in negative_shap.head(10).items():
        print(f"    {str(name):<26}{value:>+11.5f}{farmland[name]:>13.4f}")

    # ---------- Step 5: classify ----------
    def family(name: str) -> str:
        if name in BANDS:
            return "raw_bands"
        if name in INDEX_COLUMNS:
            return "spectral_indices"
        if name in TERRAIN:
            return "terrain"
        if name.startswith("ae_"):
            return "autoencoder"
        return "other"

    up_total = float(positive_shap.sum())
    up_by_family = (
        positive_shap.groupby([family(str(n)) for n in positive_shap.index]).sum().sort_values(ascending=False)
    )
    up_pct = (up_by_family / up_total * 100.0) if up_total > 0 else up_by_family * 0.0

    print("")
    print("=" * 74)
    print("STEP 5 - FAILURE CLASSIFICATION")
    print("=" * 74)
    print("  Positive-SHAP share by family:")
    for name, pct in up_pct.items():
        print(f"    {str(name):<22}{up_by_family[name]:>10.5f}{pct:>9.2f}%")

    # Case tests
    swir_close = {}
    for name in ("b11", "b12", "mn_ratio_swir"):
        ref = float(np.mean([ukwa[name], katori[name]]))
        swir_close[name] = abs(float(farmland[name]) - ref) / abs(ref) * 100.0 if ref else np.nan
    case_a = all(v <= 15.0 for v in swir_close.values() if not np.isnan(v))

    elevation = float(farmland["elevation"])
    terrain_pct = float(up_pct.get("terrain", 0.0))
    case_b = (400.0 <= elevation <= 700.0) and terrain_pct > 30.0

    ae_gap = abs(ae_norms["Farmland"] - ae_norms["Ukwa"]) / ae_norms["Ukwa"] * 100.0
    ae_pct = float(up_pct.get("autoencoder", 0.0))
    case_a_pct = float(up_pct.get("spectral_indices", 0.0)) + float(up_pct.get("raw_bands", 0.0))
    case_c = ae_gap <= 10.0 and ae_pct > max(terrain_pct, case_a_pct)

    print("")
    print("  Case A (spectral confusion):")
    for name, pct in swir_close.items():
        print(f"    {name:<20} farmland differs from positive mean by {pct:.1f}%  (<=15% qualifies)")
    print(f"    -> Case A holds: {case_a}")
    print("  Case B (terrain confusion):")
    print(f"    elevation {elevation:.1f} m in 400-700 m: {400.0 <= elevation <= 700.0}")
    print(f"    terrain share of positive SHAP: {terrain_pct:.2f}% (>30% qualifies)")
    print(f"    -> Case B holds: {case_b}")
    print("  Case C (autoencoder confusion):")
    print(f"    AE L2 norm farmland {ae_norms['Farmland']:.3f} vs Ukwa {ae_norms['Ukwa']:.3f} -> {ae_gap:.1f}% apart (<=10% qualifies)")
    print(f"    AE share of positive SHAP: {ae_pct:.2f}%")
    print(f"    -> Case C holds: {case_c}")

    holding = [n for n, ok in (("A", case_a), ("B", case_b), ("C", case_c)) if ok]
    if len(holding) > 1:
        verdict = f"Case D - compound ({'+'.join(holding)}); primary by SHAP share: {up_pct.index[0]}"
    elif holding:
        verdict = f"Case {holding[0]}"
    else:
        verdict = f"No single case qualifies; dominant positive-SHAP family is {up_pct.index[0]} at {float(up_pct.iloc[0]):.1f}%"
    print("")
    print(f"  VERDICT: {verdict}")

    payload = {
        "points": {label: {"lat": lat, "lon": lon} for label, lat, lon in POINTS},
        "predictions": {label: float(a) for (label, _, _), a in zip(POINTS, adjusted, strict=True)},
        "margins": {label: float(m) for (label, _, _), m in zip(POINTS, margins, strict=True)},
        "ae_l2_norms": ae_norms,
        "most_similar": ranked.head(15).to_dict(orient="index"),
        "most_different": ranked.dropna(subset=["scaled"]).tail(15).to_dict(orient="index"),
        "percentiles_in_positive_iqr": dict(ordered[:10]),
        "shap": {
            "base_value": base_value,
            "sum_positive": float(positive_shap.sum()),
            "sum_negative": float(negative_shap.sum()),
            "top_up": {str(k): float(v) for k, v in positive_shap.head(10).items()},
            "top_down": {str(k): float(v) for k, v in negative_shap.head(10).items()},
            "positive_share_by_family": {str(k): float(v) for k, v in up_pct.items()},
        },
        "cases": {"A": bool(case_a), "B": bool(case_b), "C": bool(case_c)},
        "verdict": verdict,
        "nan_features": nan_notes,
    }
    OUT_JSON.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    print("")
    print(f"  written to : {OUT_JSON}")


if __name__ == "__main__":
    main()
