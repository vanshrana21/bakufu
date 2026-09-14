"""
Extract the 78-dim feature vector for foreign deposits from whichever
unlabelled tile covers them.

Foreign deposits sit outside the Sausar rasters, so their spectral features and
autoencoder embeddings come from the pretraining tiles instead. Terrain features
are left NaN: the Copernicus DEM tile only covers Nagpur, and downloading global
DEM coverage is out of scope for Phase 2.5. XGBoost splits on NaN natively.

Run: python -m src.models.prospectivity.enrich_foreign
"""

from __future__ import annotations

import argparse
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
from rasterio.warp import transform_bounds
from sqlalchemy import text
from tqdm import tqdm

from src.config.settings import settings
from src.data.preprocess.compute_indices import add_indices
from src.data.preprocess.extract_features import FEATURE_COLUMNS, extract_features_bulk
from src.db.session import get_engine
from src.models.prospectivity.autoencoder import load_autoencoder
from src.models.prospectivity.enrich_features import AE_COLUMNS, embed_points

warnings.filterwarnings("ignore")

TILE_DIR: Path = settings.DATA_RAW / "satellite" / "unlabelled"
OUT_PATH: Path = settings.DATA_PROCESSED / "foreign_features_v3.parquet"

#: Terrain columns deliberately left NaN for foreign points.
TERRAIN_COLUMNS = ("elevation", "slope", "aspect")


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


def _tile_bounds() -> list[tuple[Path, tuple[float, float, float, float]]]:
    """Every tile's WGS84 bounding box, computed once."""
    entries: list[tuple[Path, tuple[float, float, float, float]]] = []
    for tile in sorted(TILE_DIR.glob("*.tif")):
        with rasterio.open(tile) as src:
            entries.append((tile, transform_bounds(src.crs, "EPSG:4326", *src.bounds)))
    return entries


def _foreign_deposits() -> pd.DataFrame:
    sql = """
        SELECT id AS deposit_id, deposit_name, country, deposit_type,
               ST_Y(geom::geometry) AS lat, ST_X(geom::geometry) AS lon
        FROM foreign_deposits
    """
    with get_engine().connect() as conn:
        rows = conn.execute(text(sql)).all()
    return pd.DataFrame(
        rows, columns=["deposit_id", "deposit_name", "country", "deposit_type", "lat", "lon"]
    )


def assign_tiles(frame: pd.DataFrame) -> pd.Series:
    """Map each deposit to the first tile whose footprint contains it."""
    tiles = _tile_bounds()
    assigned = pd.Series([None] * len(frame), index=frame.index, dtype="object")
    lat = frame["lat"].to_numpy()
    lon = frame["lon"].to_numpy()

    for tile, (left, bottom, right, top) in tiles:
        inside = (lon >= left) & (lon <= right) & (lat >= bottom) & (lat <= top)
        take = inside & assigned.isna().to_numpy()
        if take.any():
            assigned.iloc[np.flatnonzero(take)] = str(tile)
    return assigned


def enrich_foreign(out_path: Path = OUT_PATH, ae_model_path: Path | None = None) -> pd.DataFrame:
    frame = _foreign_deposits().dropna(subset=["lat", "lon"]).reset_index(drop=True)
    print(f"foreign deposits with coordinates : {len(frame)}")

    frame["tile"] = assign_tiles(frame)
    covered = frame[frame.tile.notna()].copy()
    print(f"covered by a downloaded tile      : {len(covered)}")
    if covered.empty:
        raise RuntimeError("no foreign deposit falls inside any downloaded tile")

    model = load_autoencoder(ae_model_path) if ae_model_path else load_autoencoder()
    pieces: list[pd.DataFrame] = []

    for tile_path, group in tqdm(covered.groupby("tile"), desc="tiles", unit="tile"):
        points = group[["lon", "lat"]].reset_index(drop=True)
        features = add_indices(
            extract_features_bulk(
                points, s2_path=tile_path, dem_path=dem_for_raster(tile_path)
            )
        )
        embeddings = embed_points(features, model, raster_path=tile_path)
        block = pd.concat([features.reset_index(drop=True), embeddings.reset_index(drop=True)], axis=1)
        for column in ("deposit_id", "deposit_name", "country", "deposit_type"):
            block[column] = group[column].to_numpy()
        block["tile"] = Path(tile_path).name
        pieces.append(block)

    result = pd.concat(pieces, ignore_index=True)

    # Phase 2.9: every S2 tile now has a matching Copernicus DEM, so terrain is
    # read per-tile in the loop above. The blanket NaN that used to sit here was
    # what made "terrain is missing" a near-perfect positive indicator.

    feature_columns = list(FEATURE_COLUMNS) + [
        c for c in result.columns if c.startswith(("mn_", "iron_", "clay_", "ndvi", "normalised_"))
    ]
    feature_columns = list(dict.fromkeys(feature_columns))
    result[feature_columns + AE_COLUMNS] = (
        result[feature_columns + AE_COLUMNS].apply(pd.to_numeric, errors="coerce").astype("float64")
    )

    # Tiles are written with nodata=0 and windowed reads pad short scenes with
    # zeros, so a deposit can land on an empty pixel. Its bands come back None
    # and its AE patch is mostly zeros - the same nodata shortcut that was
    # stripped from the pseudo-negatives, so hold positives to the same standard
    # and require real reflectance at the deposit pixel.
    band_columns = [c for c in FEATURE_COLUMNS if c.startswith("b")]
    on_imagery = result[band_columns].notna().all(axis=1)
    n_nodata = int((~on_imagery).sum())
    usable = result[AE_COLUMNS].notna().all(axis=1) & on_imagery
    result = result[usable].reset_index(drop=True)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    result.to_parquet(out_path, index=False)

    print("\n" + "=" * 60)
    print("FOREIGN FEATURES v3")
    print("=" * 60)
    print(f"  enriched        : {len(result)} of {len(frame)} foreign deposits")
    print(f"  dropped (on tile nodata): {n_nodata}")
    print(f"  shape           : {result.shape}")
    print(f"  distinct tiles  : {result.tile.nunique()}")
    print("  by deposit_type :")
    for deposit_type, n in result.deposit_type.value_counts().items():
        print(f"      {deposit_type:<14} {n}")
    print("  by country (top 6):")
    for country, n in result.country.value_counts().head(6).items():
        print(f"      {country:<26} {n}")
    print(f"  spectral NaNs   : {int(result[feature_columns].isna().sum().sum())}")
    print(f"  written to      : {out_path}")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default=None, help="Output parquet path")
    parser.add_argument("--ae-model", default=None, help="Autoencoder checkpoint to encode with")
    args = parser.parse_args()
    enrich_foreign(
        out_path=Path(args.output) if args.output else OUT_PATH,
        ae_model_path=Path(args.ae_model) if args.ae_model else None,
    )


if __name__ == "__main__":
    main()
