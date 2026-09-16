"""Inference service: features -> prospectivity score -> explanation.

Shared by the API routers so that endpoint code stays thin and the feature
assembly used at inference is exactly the one used in training.
"""

from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from pyproj import Transformer

from src.data.preprocess.compute_indices import add_indices
from src.data.preprocess.extract_features import extract_features_bulk
from src.models.prospectivity.autoencoder import load_autoencoder
from src.models.prospectivity.enrich_features import AE_COLUMNS, embed_points
from src.models.prospectivity.explain import explain_prediction, load_bundle
from src.config.settings import settings
from src.models.prospectivity.pu_xgboost import ALL_FEATURES, MODEL_PATH

#: The promoted bundle the service scores with. Promotion is deliberate and
#: recorded, never a side effect of a training run - the same discipline the
#: forecast models use after a training run silently replaced a shipped model.
#:
#: Promoted v1 -> v6 on 2026-09-09. v1 scored MOIL's two flagship mines at
#: essentially zero (Balaghat 0.003, Dongri Buzurg 0.056) while scoring 0.990
#: at two points whose features were entirely null, which is close to an
#: inverted map. v6 puts Balaghat and Dongri Buzurg at the cap and drops the
#: null-feature points to 0.001. Both bundles share the same 78-feature
#: schema; v6 trains on 2,399 samples with 954 positives against v1's 1,062
#: and 62. See docs/phase_4/v6_promotion_verification.md.
SHIPPED_MODEL_PATH: Path = settings.MODELS_DIR / "prospectivity_v6.pkl"

#: Overridable so another bundle can be exercised through the running API
#: without editing code. MODEL_PATH stays as the training scratch target.
_ENV_MODEL = os.environ.get("PROSPECTIVITY_MODEL")
#: The fallback, and what the process starts on. What is actually served comes
#: from active_model_path() below, which follows the registry pointer, so a
#: promotion takes effect without a restart.
ACTIVE_MODEL_PATH: Path = Path(_ENV_MODEL) if _ENV_MODEL else SHIPPED_MODEL_PATH
MODEL_VERSION: str = ACTIVE_MODEL_PATH.stem


def active_model_path() -> Path:
    """The bundle to score with now: registry pointer, env override, or shipped."""
    from src.models.registry import active_model

    return active_model().path


def active_model_version() -> str:
    """The version string reported on every scored response."""
    from src.models.registry import active_model

    return active_model().version

#: Features must come from the same mosaic the active model was trained on,
#: otherwise inference silently drifts from training. Overridable alongside
#: the model so a v2 bundle is served with the v2 raster.
_ENV_S2 = os.environ.get("PROSPECTIVITY_S2")
ACTIVE_S2_PATH: Path | None = Path(_ENV_S2) if _ENV_S2 else None

#: The encoder must match the one the active bundle was trained on, or the
#: 64 AE columns mean something different at inference than in training.
_ENV_AE = os.environ.get("PROSPECTIVITY_AE")
ACTIVE_AE_PATH: Path | None = Path(_ENV_AE) if _ENV_AE else None

#: Phase 2 has no deposit-type labels to learn from, so the type head is not
#: trained and every prediction reports "unknown". See the Phase 2 report.
DEFAULT_DEPOSIT_TYPE: str = "unknown"

MAX_BBOX_PREDICTIONS: int = 1000

#: Elkan-Noto division by c pins confident points to exactly 1.0, which reads
#: as certainty the data cannot support. Cap the reported score just below.
SCORE_CAP: float = 0.99


def cap_score(value):
    """Clamp a score (scalar or array) into [0.0, SCORE_CAP]."""
    return np.clip(value, 0.0, SCORE_CAP)

_AE_CACHE: dict[str, Any] = {}
_AE_LOCK = threading.Lock()


def _autoencoder():
    if "model" not in _AE_CACHE:
        with _AE_LOCK:
            if "model" not in _AE_CACHE:
                _AE_CACHE["model"] = (
                    load_autoencoder(ACTIVE_AE_PATH) if ACTIVE_AE_PATH else load_autoencoder()
                )
    return _AE_CACHE["model"]


def _covering_tile(lon: float, lat: float) -> Path | None:
    """First unlabelled tile whose footprint contains the point, if any.

    v4 trains on national NGDR records, so inference has to resolve rasters
    beyond the Sausar mosaic or every out-of-belt query 404s.
    """
    from src.data import raster_pool

    tile_dir = settings.DATA_RAW / "satellite" / "unlabelled"
    for tile in sorted(tile_dir.glob("*.tif")):
        try:
            # Footprints are cached per file version; this used to open every
            # tile for every point that missed the primary mosaic.
            left, bottom, right, top = raster_pool.wgs84_bounds(tile)
        except Exception:  # noqa: BLE001 - unreadable tile must not break serving
            continue
        if left <= lon <= right and bottom <= lat <= top:
            return tile
    return None


def build_feature_frame(points: pd.DataFrame) -> pd.DataFrame:
    """Assemble the 78-dim feature frame for points with lon/lat columns."""
    points = points.reset_index(drop=True)
    frame = add_indices(extract_features_bulk(points, s2_path=ACTIVE_S2_PATH))
    embeddings = embed_points(frame, _autoencoder(), raster_path=ACTIVE_S2_PATH)
    frame = pd.concat([frame, embeddings], axis=1)

    # Points outside the primary mosaic fall back to whichever national tile
    # covers them, matching how their training features were built.
    missing = frame[AE_COLUMNS].isna().all(axis=1)
    for index in frame.index[missing]:
        tile = _covering_tile(float(points.lon[index]), float(points.lat[index]))
        if tile is None:
            continue
        one = points.loc[[index], ["lon", "lat"]].reset_index(drop=True)
        tile_frame = add_indices(extract_features_bulk(one, s2_path=tile))
        tile_embed = embed_points(tile_frame, _autoencoder(), raster_path=tile)
        for column in tile_frame.columns:
            if column in frame.columns:
                frame.loc[index, column] = tile_frame.iloc[0][column]
        frame.loc[index, AE_COLUMNS] = tile_embed.iloc[0].to_numpy()

    return frame


def uncertainty_from_probability(p: float | np.ndarray) -> float | np.ndarray:
    """Distance-from-decision-boundary uncertainty in [0, 1].

    1.0 at p=0.5 (model is maximally undecided), 0.0 at p=0 or p=1.
    """
    return 1.0 - np.abs(2.0 * np.asarray(p) - 1.0)


def score_frame(
    frame: pd.DataFrame,
    model_path: Path | str | None = None,
    adjust: bool = True,
) -> np.ndarray:
    """Predicted probabilities, optionally Elkan-Noto adjusted."""
    bundle = load_bundle(model_path or active_model_path())
    X = frame.reindex(columns=bundle["features"]).astype("float64")
    # Bundles trained with a missing-value sentinel must be served the same way,
    # or absent terrain reaches the trees as NaN instead of the value they split on.
    for column, value in (bundle.get("fill_values") or {}).items():
        if column in X.columns:
            X[column] = X[column].fillna(value)
    p = bundle["model"].predict_proba(X)[:, 1]
    if adjust:
        c = float(bundle.get("elkan_noto_c") or 1.0)
        p = np.clip(p / max(c, 1e-6), 0.0, 1.0)
    return p


def predict_point(
    lat: float,
    lon: float,
    model_path: Path | str | None = None,
    explain: bool = True,
) -> dict[str, Any] | None:
    """Score one location. Returns None if it falls outside the raster."""
    points = pd.DataFrame([{"lon": lon, "lat": lat}])
    frame = build_feature_frame(points)

    if frame[AE_COLUMNS].isna().all(axis=1).iloc[0]:
        return None

    model_path = model_path or active_model_path()
    score = float(cap_score(score_frame(frame, model_path)[0]))
    bundle = load_bundle(model_path)
    row = frame.reindex(columns=bundle["features"]).astype("float64")

    shap_top5: list[dict[str, Any]] = []
    if explain:
        shap_top5 = explain_prediction(row.iloc[0], model_path)["top_5_features"]

    extracted = {
        column: (None if pd.isna(frame.iloc[0][column]) else float(frame.iloc[0][column]))
        for column in ALL_FEATURES
        if column in frame.columns and not column.startswith("ae_")
    }

    return {
        "prospectivity_score": score,
        "predicted_type": DEFAULT_DEPOSIT_TYPE,
        "uncertainty": float(uncertainty_from_probability(score)),
        "features_extracted": extracted,
        "shap_top5": shap_top5,
        "model_version": active_model_version(),
        "lat": lat,
        "lon": lon,
    }


def grid_points(
    min_lon: float,
    min_lat: float,
    max_lon: float,
    max_lat: float,
    grid_resolution_m: int = 100,
    cap: int = MAX_BBOX_PREDICTIONS,
) -> pd.DataFrame:
    """Regular grid over a bbox, spaced `grid_resolution_m` on the ground.

    Spacing is computed in a metric CRS then converted back to WGS84, so cells
    stay square regardless of latitude. If the grid would exceed `cap` cells,
    the step is widened so the whole bbox is still covered.
    """
    mid_lat = (min_lat + max_lat) / 2.0
    utm_zone = int((((min_lon + max_lon) / 2.0) + 180) // 6) + 1
    epsg = (32600 if mid_lat >= 0 else 32700) + utm_zone
    to_m = Transformer.from_crs("EPSG:4326", f"EPSG:{epsg}", always_xy=True)
    to_deg = Transformer.from_crs(f"EPSG:{epsg}", "EPSG:4326", always_xy=True)

    x0, y0 = to_m.transform(min_lon, min_lat)
    x1, y1 = to_m.transform(max_lon, max_lat)
    width, height = abs(x1 - x0), abs(y1 - y0)

    def _axes(step: float) -> tuple[np.ndarray, np.ndarray]:
        return (
            np.arange(min(x0, x1), max(x0, x1) + step, step),
            np.arange(min(y0, y1), max(y0, y1) + step, step),
        )

    step = float(grid_resolution_m)
    xs, ys = _axes(step)
    if xs.size * ys.size > cap:
        # Widen the step until the whole bbox fits under the cap. The closed
        # form undershoots slightly because each axis is inclusive of its end,
        # so nudge it up until it genuinely fits rather than truncating the
        # grid and silently dropping coverage of the eastern/northern edge.
        step = float(np.sqrt(width * height / cap))
        xs, ys = _axes(step)
        while xs.size * ys.size > cap:
            step *= 1.05
            xs, ys = _axes(step)
    grid_x, grid_y = np.meshgrid(xs, ys)
    lons, lats = to_deg.transform(grid_x.ravel(), grid_y.ravel())

    frame = pd.DataFrame({"lon": lons, "lat": lats})
    return frame.head(cap), step


def predict_bbox(
    min_lon: float,
    min_lat: float,
    max_lon: float,
    max_lat: float,
    grid_resolution_m: int = 100,
    model_path: Path | str | None = None,
) -> dict[str, Any]:
    """Score a grid over a bbox, highest first."""
    points, step = grid_points(min_lon, min_lat, max_lon, max_lat, grid_resolution_m)
    frame = build_feature_frame(points)

    inside = frame[AE_COLUMNS].notna().all(axis=1).to_numpy()
    scores = np.full(len(frame), np.nan)
    if inside.any():
        scores[inside] = cap_score(score_frame(frame[inside], model_path or active_model_path()))

    result = pd.DataFrame(
        {
            "lon": points.lon.to_numpy(),
            "lat": points.lat.to_numpy(),
            "score": scores,
            "type": DEFAULT_DEPOSIT_TYPE,
        }
    ).dropna(subset=["score"])
    result = result.sort_values("score", ascending=False)

    return {
        "predictions": result.to_dict(orient="records"),
        "count": int(len(result)),
        "bbox": [min_lon, min_lat, max_lon, max_lat],
        "grid_resolution_m": float(step),
        "cells_outside_raster": int((~inside).sum()),
        "model_version": active_model_version(),
    }


def heatmap_grid(
    min_lon: float,
    min_lat: float,
    max_lon: float,
    max_lat: float,
    grid_size: int = 32,
    model_path: Path | str | None = None,
) -> dict[str, Any]:
    """Score a regular lat/lon lattice aligned exactly to the bbox.

    `predict_bbox` cannot feed a map: it builds its grid in projected metres
    and reprojects per point, so cells do not share row latitudes, some fall
    outside the requested bbox, and the list is sorted by score rather than
    position. This walks a lattice in degrees instead, so the result reshapes
    into `grid_size` x `grid_size` and drops straight onto a map overlay.

    A cell is None when it lies outside the imagery footprint *or* when every
    feature for it came back null. The second case matters: the older v1
    bundle scored an all-null feature vector at the 0.99 cap, which would have
    painted the brightest hotspots where nothing was measured.
    """
    cell_w = (max_lon - min_lon) / grid_size
    cell_h = (max_lat - min_lat) / grid_size
    lons = min_lon + (np.arange(grid_size) + 0.5) * cell_w
    lats = max_lat - (np.arange(grid_size) + 0.5) * cell_h  # top-left origin

    mesh_lon, mesh_lat = np.meshgrid(lons, lats)
    points = pd.DataFrame({"lon": mesh_lon.ravel(), "lat": mesh_lat.ravel()})
    frame = build_feature_frame(points)

    usable = frame[AE_COLUMNS].notna().all(axis=1).to_numpy()
    scores = np.full(len(frame), np.nan)
    if usable.any():
        scores[usable] = cap_score(score_frame(frame[usable], model_path or active_model_path()))

    grid = scores.reshape(grid_size, grid_size)
    outside = int(np.isnan(grid).sum())
    finite = grid[~np.isnan(grid)]

    return {
        "bbox": [min_lon, min_lat, max_lon, max_lat],
        "grid": {
            "n_cols": grid_size,
            "n_rows": grid_size,
            "cell_width_deg": cell_w,
            "cell_height_deg": cell_h,
            "origin": "top_left",
        },
        # float32 clipping leaves values a whisker above the cap
        # (0.9900000095367432), which would break the documented
        # "never greater than 0.99" guarantee the map legend relies on.
        "scores": [
            [None if np.isnan(v) else min(float(v), float(SCORE_CAP)) for v in row]
            for row in grid
        ],
        "cells": {
            "cells_total": int(grid.size),
            "cells_outside_raster": outside,
            "cells_masked_out": 0,
            "cells_scored": int(grid.size - outside),
        },
        "score_range": {
            "min": float(finite.min()) if finite.size else None,
            "max": min(float(finite.max()), float(SCORE_CAP)) if finite.size else None,
            "cap": float(SCORE_CAP),
        },
        "model_version": Path(model_path).stem if model_path else active_model_version(),
    }
