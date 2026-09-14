"""
Why does Balaghat (21.80, 80.20) score ~0 when it sits on a known Mn belt?

Walks the full inference path at that coordinate - raw pixels, patch stats,
autoencoder embedding, terrain, the 78 assembled features, the raw XGBoost
margin, and the Elkan-Noto-adjusted probability - so the cause can be
attributed to a nodata gap, an encoder failure, or genuinely negative-looking
features.

Run: python -m scripts.diagnostics.debug_balaghat
"""

from __future__ import annotations

import json
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
from pyproj import Transformer

from src.config.settings import settings
from src.data.preprocess.compute_indices import add_indices
from src.data.preprocess.extract_features import extract_features_bulk
from src.models.prospectivity.autoencoder import load_autoencoder
from src.models.prospectivity.enrich_features import AE_COLUMNS, embed_points, read_patch
from src.models.prospectivity.explain import load_bundle

warnings.filterwarnings("ignore")

TARGET = (21.80, 80.20)  # lat, lon
NEARBY = [(21.79, 80.19), (21.81, 80.21), (21.78, 80.22)]

S2_PATH: Path = settings.DATA_RAW / "satellite" / "s2_sausar_v2.tif"
MODEL_PATH: Path = settings.MODELS_DIR / "prospectivity_v4.pkl"
AE_PATH: Path = settings.MODELS_DIR / "autoencoder_v1.pt"
OUT_PATH: Path = settings.DATA_PROCESSED / "debug_balaghat.json"

BAND_NAMES = ["b02", "b03", "b04", "b08", "b11", "b12"]


def probe(lat: float, lon: float, model, bundle) -> dict[str, object]:
    """Full inference walk at one coordinate."""
    report: dict[str, object] = {"lat": lat, "lon": lon}

    # 1. raw pixel values
    with rasterio.open(S2_PATH) as src:
        to_raster = Transformer.from_crs("EPSG:4326", src.crs, always_xy=True)
        x, y = to_raster.transform(lon, lat)
        inside = (src.bounds.left <= x <= src.bounds.right) and (
            src.bounds.bottom <= y <= src.bounds.top
        )
        report["inside_raster"] = bool(inside)
        if inside:
            row, col = src.index(x, y)
            report["pixel_rowcol"] = [int(row), int(col)]
            values = [float(v) for v in next(src.sample([(x, y)]))]
            report["raw_pixel"] = dict(zip(BAND_NAMES, values, strict=True))
            report["pixel_all_zero"] = bool(all(v == 0 for v in values))

    # 2. patch statistics
    patch = read_patch(lon, lat, S2_PATH)
    if patch is None:
        report["patch"] = None
    else:
        report["patch"] = {
            "shape": list(patch.shape),
            "zero_fraction": float((patch == 0).mean()),
            "per_band_zero_fraction": {
                name: float((patch[i] == 0).mean()) for i, name in enumerate(BAND_NAMES)
            },
            "min": float(patch.min()),
            "max": float(patch.max()),
            "mean": float(patch.mean()),
        }

    # 3-5. assembled features
    points = pd.DataFrame([{"lon": lon, "lat": lat}])
    frame = add_indices(extract_features_bulk(points, s2_path=S2_PATH))
    embeddings = embed_points(frame, model, raster_path=S2_PATH)
    frame = pd.concat([frame, embeddings], axis=1)

    ae_values = embeddings.iloc[0].to_numpy(dtype="float64")
    report["autoencoder"] = {
        "all_nan": bool(np.isnan(ae_values).all()),
        "nonzero_dims": int(np.count_nonzero(np.nan_to_num(ae_values))),
        "of_dims": len(AE_COLUMNS),
        "min": None if np.isnan(ae_values).all() else float(np.nanmin(ae_values)),
        "max": None if np.isnan(ae_values).all() else float(np.nanmax(ae_values)),
    }
    report["terrain"] = {
        key: (None if pd.isna(frame.iloc[0].get(key)) else float(frame.iloc[0][key]))
        for key in ("elevation", "slope", "aspect")
    }
    report["spectral"] = {
        key: (None if pd.isna(frame.iloc[0].get(key)) else float(frame.iloc[0][key]))
        for key in BAND_NAMES
        + ["mn_ratio_swir", "iron_ratio", "ferrous_ratio", "ndvi", "normalised_burn_ratio_swir"]
    }

    # 6-7. model output
    features = bundle["features"]
    X = frame.reindex(columns=features).astype("float64")
    for column, value in (bundle.get("fill_values") or {}).items():
        if column in X.columns:
            X[column] = X[column].fillna(value)
    report["n_features_nan"] = int(X.isna().sum().sum())

    booster_model = bundle["model"]
    margin = float(booster_model.predict(X, output_margin=True)[0])
    raw_prob = float(booster_model.predict_proba(X)[:, 1][0])
    c = float(bundle.get("elkan_noto_c") or 1.0)
    adjusted = float(np.clip(raw_prob / max(c, 1e-6), 0.0, 1.0))
    report["model"] = {
        "raw_margin": margin,
        "raw_probability": raw_prob,
        "elkan_noto_c": c,
        "adjusted_probability": adjusted,
    }
    return report


def main() -> None:
    model = load_autoencoder(AE_PATH)
    bundle = load_bundle(MODEL_PATH)

    results: list[dict[str, object]] = []
    primary = probe(*TARGET, model=model, bundle=bundle)
    results.append(primary)

    print("=" * 70)
    print(f"BALAGHAT DEBUG  ({TARGET[0]}, {TARGET[1]})")
    print("=" * 70)
    print(f"  inside raster     : {primary['inside_raster']}")
    print(f"  raw pixel         : {primary.get('raw_pixel')}")
    print(f"  all bands zero    : {primary.get('pixel_all_zero')}")
    patch = primary.get("patch")
    if patch:
        print(f"  patch zero frac   : {patch['zero_fraction']:.4f}")
        print(f"  patch min/max/mean: {patch['min']:.4f} / {patch['max']:.4f} / {patch['mean']:.4f}")
    ae = primary["autoencoder"]
    print(f"  AE nonzero dims   : {ae['nonzero_dims']} / {ae['of_dims']}  (all NaN: {ae['all_nan']})")
    print(f"  terrain           : {primary['terrain']}")
    print(f"  feature NaNs      : {primary['n_features_nan']}")
    model_out = primary["model"]
    print(f"  raw margin        : {model_out['raw_margin']:.5f}")
    print(f"  raw probability   : {model_out['raw_probability']:.6f}")
    print(f"  Elkan-Noto c      : {model_out['elkan_noto_c']:.4f}")
    print(f"  adjusted prob     : {model_out['adjusted_probability']:.6f}")

    print("")
    print("  spectral features:")
    for key, value in primary["spectral"].items():
        print(f"    {key:<28} {value}")

    # Only walk the neighbours when the primary pixel is genuinely empty.
    if primary.get("pixel_all_zero"):
        print("")
        print("  primary pixel is all-zero - probing neighbours:")
        for lat, lon in NEARBY:
            alt = probe(lat, lon, model=model, bundle=bundle)
            results.append(alt)
            print(
                f"    ({lat}, {lon}) all_zero={alt.get('pixel_all_zero')} "
                f"score={alt['model']['adjusted_probability']:.6f}"
            )
            if not alt.get("pixel_all_zero"):
                print(f"    -> first valid coordinate: ({lat}, {lon})")
                break

    OUT_PATH.write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
    print("")
    print(f"  written to        : {OUT_PATH}")


if __name__ == "__main__":
    main()
