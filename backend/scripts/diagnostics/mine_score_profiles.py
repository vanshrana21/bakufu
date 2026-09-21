"""Score profile for each MOIL mine, for the pitch narrative.

Per mine: the served score, its two strongest SHAP drivers, how far the
nearest v6 training positive is, and what the surrounding ground scores. The
last two matter for reading a moderate score: a point 1.5 km from a known
deposit scoring 0.34 means something different depending on whether its
neighbours score 0.9 or 0.3.

Writes data/processed/mine_score_profiles.json and prints the table.

Run: python -m scripts.diagnostics.mine_score_profiles
"""

from __future__ import annotations

import json
import warnings

import joblib
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

from src.config.settings import settings
from src.models.prospectivity.predict import (
    ACTIVE_MODEL_PATH,
    SCORE_CAP,
    build_feature_frame,
)
from scripts.diagnostics.debug_balaghat_new_coords import haversine_km, positive_class

OUT = settings.DATA_PROCESSED / "mine_score_profiles.json"

#: Half-width of the neighbourhood probe, in degrees (~1.1 km).
NEIGHBOURHOOD_DEG = 0.01
#: Balaghat sensitivity grid: 5 x 5 points spanning about +/- 2 km.
SENSITIVITY_DEG = 0.02

HUMAN = {
    "elevation": "elevation",
    "slope": "slope",
    "aspect": "slope aspect",
    "b02": "blue reflectance",
    "b03": "green reflectance",
    "b04": "red reflectance",
    "b08": "near-infrared reflectance",
    "b11": "SWIR-1 reflectance",
    "b12": "SWIR-2 reflectance",
    "mn_ratio_swir": "SWIR-1/SWIR-2 ratio (Mn-oxide proxy)",
    "iron_ratio": "red/green ratio (ferric-iron proxy)",
    "ferrous_ratio": "SWIR-1/NIR ratio (ferrous proxy)",
    "ndvi": "NDVI (vegetation)",
    "normalised_burn_ratio_swir": "NIR/SWIR-2 normalised difference",
}


def label(feature: str) -> str:
    if feature.startswith("ae_"):
        return f"texture/context embedding dim {feature[3:]}"
    return HUMAN.get(feature, feature)


def score_points(points: pd.DataFrame, model, order, c) -> tuple[np.ndarray, np.ndarray]:
    """Adjusted scores plus the SHAP matrix for a lon/lat frame."""
    import shap

    frame = build_feature_frame(points)
    design = frame.reindex(columns=order).astype("float64")
    raw = model.predict_proba(design)[:, 1]
    adjusted = np.clip(np.clip(raw / max(c, 1e-6), 0.0, 1.0), 0.0, SCORE_CAP)
    usable = frame.reindex(columns=["b02"]).notna().to_numpy().ravel()
    adjusted = np.where(usable, adjusted, np.nan)
    shap_values = shap.TreeExplainer(model).shap_values(design)
    return adjusted, shap_values


def main() -> None:
    bundle = joblib.load(ACTIVE_MODEL_PATH)
    model, order = bundle["model"], list(bundle["features"])
    c = float(bundle.get("elkan_noto_c") or 1.0)

    mines = settings.MOIL_MINES
    names = list(mines)
    points = pd.DataFrame(
        [{"lon": mines[n]["lon"], "lat": mines[n]["lat"]} for n in names]
    )
    scores, shap_values = score_points(points, model, order, c)

    positives = positive_class()

    # Neighbourhood: the four points ~1.1 km N/S/E/W of each mine.
    offsets = [(NEIGHBOURHOOD_DEG, 0.0), (-NEIGHBOURHOOD_DEG, 0.0),
               (0.0, NEIGHBOURHOOD_DEG), (0.0, -NEIGHBOURHOOD_DEG)]
    neighbour_points = pd.DataFrame(
        [
            {"lon": mines[n]["lon"] + dlon, "lat": mines[n]["lat"] + dlat}
            for n in names
            for dlat, dlon in offsets
        ]
    )
    neighbour_scores, _ = score_points(neighbour_points, model, order, c)
    neighbour_scores = neighbour_scores.reshape(len(names), len(offsets))

    profiles = []
    for index, name in enumerate(names):
        mine = mines[name]
        distances = haversine_km(mine["lat"], mine["lon"], positives.lat, positives.lon)
        nearest = int(np.argmin(distances))
        row = pd.Series(shap_values[index], index=order)
        top = row.reindex(row.abs().sort_values(ascending=False).index).head(2)
        neighbours = neighbour_scores[index]
        profiles.append(
            {
                "mine": name,
                "state": mine["state"],
                "type": mine["type"],
                "confidence": mine["confidence"],
                "lat": mine["lat"],
                "lon": mine["lon"],
                "score": None if np.isnan(scores[index]) else round(float(scores[index]), 4),
                "nearest_positive_km": round(float(distances[nearest]), 2),
                "nearest_positive_source": str(positives.source.iloc[nearest]),
                "positives_within_5km": int((distances <= 5.0).sum()),
                "neighbourhood_min": round(float(np.nanmin(neighbours)), 4),
                "neighbourhood_max": round(float(np.nanmax(neighbours)), 4),
                "neighbourhood_mean": round(float(np.nanmean(neighbours)), 4),
                "shap_top2": [
                    {
                        "feature": feature,
                        "label": label(feature),
                        "shap": round(float(value), 4),
                        "direction": "raises" if value > 0 else "lowers",
                    }
                    for feature, value in top.items()
                ],
            }
        )

    # Balaghat sensitivity: is 0.34 a local dip or the whole block?
    balaghat = mines["Balaghat"]
    steps = np.linspace(-SENSITIVITY_DEG, SENSITIVITY_DEG, 5)
    grid = pd.DataFrame(
        [
            {"lon": balaghat["lon"] + dlon, "lat": balaghat["lat"] + dlat}
            for dlat in steps
            for dlon in steps
        ]
    )
    grid_scores, _ = score_points(grid, model, order, c)

    # What do the positives nearest Balaghat score themselves?
    distances = haversine_km(balaghat["lat"], balaghat["lon"], positives.lat, positives.lon)
    closest = positives.iloc[np.argsort(distances)[:5]]
    closest_scores, _ = score_points(
        closest[["lon", "lat"]].reset_index(drop=True), model, order, c
    )

    payload = {
        "model": ACTIVE_MODEL_PATH.name,
        "positives": int(len(positives)),
        "profiles": profiles,
        "balaghat_sensitivity": {
            "span_deg": SENSITIVITY_DEG,
            "min": round(float(np.nanmin(grid_scores)), 4),
            "max": round(float(np.nanmax(grid_scores)), 4),
            "mean": round(float(np.nanmean(grid_scores)), 4),
            "above_0_85_pct": round(float(np.nanmean(grid_scores >= 0.85) * 100), 1),
            "grid": [round(float(v), 4) for v in grid_scores],
        },
        "balaghat_nearest_positives": [
            {
                "source": str(row.source),
                "km": round(float(sorted(distances)[i]), 2),
                "score": round(float(closest_scores[i]), 4),
            }
            for i, (_, row) in enumerate(closest.iterrows())
        ],
    }
    OUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print(f"{'mine':16}{'score':>8}{'conf':>12}{'near_km':>9}{'nbr_min':>9}{'nbr_max':>9}  drivers")
    for profile in sorted(profiles, key=lambda p: -(p["score"] or 0)):
        drivers = ", ".join(
            f"{d['label']} ({d['shap']:+.2f})" for d in profile["shap_top2"]
        )
        print(
            f"{profile['mine']:16}{profile['score']:>8}{profile['confidence']:>12}"
            f"{profile['nearest_positive_km']:>9}{profile['neighbourhood_min']:>9}"
            f"{profile['neighbourhood_max']:>9}  {drivers}"
        )
    print("")
    print("Balaghat sensitivity grid:", payload["balaghat_sensitivity"]["min"], "-",
          payload["balaghat_sensitivity"]["max"], "mean",
          payload["balaghat_sensitivity"]["mean"],
          f"({payload['balaghat_sensitivity']['above_0_85_pct']}% >= 0.85)")
    print("Balaghat nearest positives:", payload["balaghat_nearest_positives"])
    print(f"written: {OUT}")


if __name__ == "__main__":
    main()
