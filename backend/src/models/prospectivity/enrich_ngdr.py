"""
For each of ~622 NGDR national records, extract features using
whichever tile covers its location. Reuses enrich logic from Phase 2.5.

Encoding uses autoencoder_v1.pt deliberately: the Phase 2.7 adversarial
variant diverged (country loss ~1e6, embeddings at 1e8 scale) and is not
used here.

Run: python -m src.models.prospectivity.enrich_ngdr
"""

from __future__ import annotations

import argparse
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
from rasterio.warp import transform_bounds

from src.config.settings import settings
from src.data.preprocess.compute_indices import INDEX_COLUMNS, add_indices
from src.data.preprocess.extract_features import FEATURE_COLUMNS, extract_features_bulk
from src.data.ingest.cluster_ngdr_for_tiles import load_ngdr
from src.models.prospectivity.autoencoder import MODEL_PATH as AE_V1_PATH
from src.models.prospectivity.autoencoder import load_autoencoder
from src.models.prospectivity.enrich_features import AE_COLUMNS, embed_points

warnings.filterwarnings("ignore")

TILE_DIR: Path = settings.DATA_RAW / "satellite" / "unlabelled"
SAUSAR_V2: Path = settings.DATA_RAW / "satellite" / "s2_sausar_v2.tif"
OUT_PATH: Path = settings.DATA_PROCESSED / "ngdr_features_v5.parquet"

BASE_FEATURES: list[str] = FEATURE_COLUMNS + INDEX_COLUMNS

#: Confidence in an NGDR record as a positive, by how precisely it is located.
#: A native point with a known deposit type is the strongest; a lease polygon
#: reduced to a representative point is the weakest.
WEIGHT_POINT_TYPED: float = 0.8
WEIGHT_POINT_UNTYPED: float = 0.7
WEIGHT_POLY_EXPLORATION: float = 0.6
WEIGHT_POLY_LEASE: float = 0.5
WEIGHT_OTHER: float = 0.4


#: Per-tile Copernicus DEM written by src.data.ingest.download_global_dem.
GLOBAL_DEM_DIR: Path = settings.DATA_RAW / "dem" / "global"


def dem_for_raster(raster_path: Path | str | None) -> Path | None:
    """Matching global DEM for an S2 tile, or None to fall back to the default.

    Composited tiles are named <stem>_v2.tif but share the original's footprint,
    so they reuse the same DEM rather than needing their own download.
    """
    if raster_path is None:
        return None
    stem = Path(raster_path).stem
    candidate = GLOBAL_DEM_DIR / f"dem_{stem}.tif"
    if candidate.exists():
        return candidate
    if stem.endswith("_v2"):
        base = GLOBAL_DEM_DIR / f"dem_{stem[:-3]}.tif"
        if base.exists():
            return base
    return None


def assign_weight(row: pd.Series) -> float:
    """Per-record confidence weight from geometry provenance and typing."""
    geometry_type = str(row.get("source_geometry_type") or "")
    layer = str(row.get("source_layer") or "").lower()
    deposit_type = row.get("deposit_type")
    typed = deposit_type not in (None, "", "UNKNOWN") and not pd.isna(deposit_type)

    if geometry_type == "point":
        return WEIGHT_POINT_TYPED if typed else WEIGHT_POINT_UNTYPED
    if geometry_type == "polygon_centroid":
        if "exploration" in layer:
            return WEIGHT_POLY_EXPLORATION
        if "lease" in layer:
            return WEIGHT_POLY_LEASE
    return WEIGHT_OTHER


def _tile_bounds(path: Path) -> tuple[float, float, float, float]:
    with rasterio.open(path) as src:
        return transform_bounds(src.crs, "EPSG:4326", *src.bounds)


def assign_tiles(frame: pd.DataFrame) -> pd.Series:
    """Which raster covers each record.

    The Sausar mosaic is checked first - it is 20 m rather than 60 m and has a
    matching DEM, so it yields terrain features the 60 m tiles cannot.
    """
    assignment = pd.Series([None] * len(frame), index=frame.index, dtype="object")
    lat = frame["lat"].to_numpy()
    lon = frame["lon"].to_numpy()

    rasters: list[tuple[str, Path]] = [("__sausar__", SAUSAR_V2)]
    # Prefer the Phase 2.9 multi-scene composites: an original and its _v2 share
    # a footprint, but the composite has the swath gaps filled, so a record that
    # fell on nodata in the original may now sit on real imagery.
    tiles = sorted(TILE_DIR.glob("*.tif"))
    composited = {t.stem[:-3] for t in tiles if t.stem.endswith("_v2")}
    tiles = [t for t in tiles if t.stem.endswith("_v2") or t.stem not in composited]
    tiles.sort(key=lambda t: (not t.stem.endswith("_v2"), t.name))
    rasters += [(t.name, t) for t in tiles]

    for label, path in rasters:
        pending = assignment.isna().to_numpy()
        if not pending.any():
            break
        left, bottom, right, top = _tile_bounds(path)
        inside = pending & (lon >= left) & (lon <= right) & (lat >= bottom) & (lat <= top)
        if inside.any():
            assignment.iloc[np.flatnonzero(inside)] = label
    return assignment


def enrich_ngdr(out_path: Path = OUT_PATH, ae_model_path: Path = AE_V1_PATH) -> pd.DataFrame:
    frame = load_ngdr().dropna(subset=["lat", "lon"]).reset_index(drop=True)
    print(f"NGDR records loaded : {len(frame)}")

    frame["weight"] = frame.apply(assign_weight, axis=1)
    frame["tile"] = assign_tiles(frame)

    covered = frame[frame.tile.notna()].copy()
    uncovered = frame[frame.tile.isna()]
    print(f"covered by a raster : {len(covered)}")
    print(f"uncovered           : {len(uncovered)}")

    model = load_autoencoder(ae_model_path)

    pieces: list[pd.DataFrame] = []
    for tile_label, group in covered.groupby("tile"):
        raster = SAUSAR_V2 if tile_label == "__sausar__" else TILE_DIR / str(tile_label)
        points = group[["lon", "lat"]].reset_index(drop=True)

        # Terrain only resolves inside the Sausar DEM footprint; elsewhere the
        # extractor returns None and the columns stay NaN, which XGBoost handles.
        features = add_indices(
            extract_features_bulk(
                points, s2_path=raster, dem_path=dem_for_raster(raster)
            )
        )
        embeddings = embed_points(features, model, raster_path=raster)

        block = pd.concat(
            [group.reset_index(drop=True), features.drop(columns=["lon", "lat"], errors="ignore"), embeddings],
            axis=1,
        )
        pieces.append(block)

    result = pd.concat(pieces, ignore_index=True) if pieces else pd.DataFrame()

    # Same validity standard as the foreign positives: a record sitting on a
    # nodata pixel has no real reflectance and its patch encodes emptiness.
    band_columns = [c for c in FEATURE_COLUMNS if c.startswith("b")]
    on_imagery = result[band_columns].notna().all(axis=1)
    has_embedding = result[AE_COLUMNS].notna().all(axis=1)
    n_nodata = int((~(on_imagery & has_embedding)).sum())
    result = result[on_imagery & has_embedding].reset_index(drop=True)

    keep = (
        ["ngdr_id", "state", "source_layer", "source_geometry_type", "deposit_type",
         "weight", "lat", "lon", "tile"]
        + BASE_FEATURES
        + AE_COLUMNS
    )
    result = result[[c for c in keep if c in result.columns]]
    for column in BASE_FEATURES + AE_COLUMNS:
        if column in result.columns:
            result[column] = pd.to_numeric(result[column], errors="coerce").astype("float64")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    result.to_parquet(out_path, index=False)

    print("")
    print("=" * 68)
    print("NGDR FEATURES v5")
    print("=" * 68)
    print(f"  records processed  : {len(frame)}")
    print(f"  enriched           : {len(result)}")
    print(f"  uncovered (no tile): {len(uncovered)}")
    print(f"  dropped (nodata)   : {n_nodata}")
    print(f"  shape              : {result.shape}")
    print(f"  distinct rasters   : {result.tile.nunique() if len(result) else 0}")

    if len(result):
        print("")
        print("  weight distribution:")
        for weight, count in sorted(result.weight.value_counts().items()):
            bar = "#" * int(count / max(result.weight.value_counts().max(), 1) * 40)
            print(f"    {weight:.1f}  {count:>4}  {bar}")

        print("")
        print("  geometry type:")
        for geometry_type, count in result.source_geometry_type.value_counts().items():
            print(f"    {str(geometry_type):<18} {count}")

        print("")
        print("  per-state coverage (enriched / total):")
        totals = frame.state.fillna("UNKNOWN").value_counts()
        got = result.state.fillna("UNKNOWN").value_counts()
        for state in sorted(totals.index):
            print(f"    {str(state)[:30]:<32} {int(got.get(state, 0)):>4} / {int(totals[state]):>4}")

        terrain = ["elevation", "slope", "aspect"]
        n_terrain = int(result[terrain].notna().all(axis=1).sum())
        print("")
        print(f"  with terrain features : {n_terrain} (rest NaN - outside the Sausar DEM)")

    print(f"  written to         : {out_path}")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default=None, help="Output parquet path")
    parser.add_argument("--ae-model", default=None, help="Autoencoder checkpoint")
    args = parser.parse_args()
    enrich_ngdr(
        out_path=Path(args.output) if args.output else OUT_PATH,
        ae_model_path=Path(args.ae_model) if args.ae_model else AE_V1_PATH,
    )


if __name__ == "__main__":
    main()
