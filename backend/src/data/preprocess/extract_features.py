"""Sample Sentinel-2 reflectance and DEM terrain attributes at point locations."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import rasterio
from rasterio.io import DatasetReader

from src.config.settings import S2_BANDS, settings
from src.data import raster_pool

#: Feature columns produced by this module, in order.
BAND_FEATURES: list[str] = [band.lower() for band in S2_BANDS]
TERRAIN_FEATURES: list[str] = ["elevation", "slope", "aspect"]
FEATURE_COLUMNS: list[str] = BAND_FEATURES + TERRAIN_FEATURES

#: Column name per Sentinel-2 band index (1-based), e.g. {1: "b02", ...}.
BAND_COLUMNS: dict[int, str] = {i + 1: band.lower() for i, band in enumerate(S2_BANDS)}


def _is_nodata(value: float, nodata: float | None) -> bool:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return True
    return nodata is not None and float(value) == float(nodata)


def _sample_bands(src: DatasetReader, xs: list[float], ys: list[float]) -> list[dict[str, float | None]]:
    """Sample every band at the given dataset-CRS coordinates."""
    rows: list[dict[str, float | None]] = []
    nodata = src.nodata
    for values in src.sample(list(zip(xs, ys, strict=True))):
        row: dict[str, float | None] = {}
        for band_index, column in BAND_COLUMNS.items():
            raw = values[band_index - 1]
            row[column] = None if _is_nodata(float(raw), nodata) else float(raw)
        rows.append(row)
    return rows


def _terrain_at(src: DatasetReader, x: float, y: float) -> dict[str, float | None]:
    """Elevation plus slope/aspect from the 3x3 DEM neighbourhood (Horn's method)."""
    empty: dict[str, float | None] = {"elevation": None, "slope": None, "aspect": None}

    row, col = src.index(x, y)
    if not (0 <= row < src.height and 0 <= col < src.width):
        return empty

    # Clamp the 3x3 window so points on the raster edge still yield an elevation.
    row0, col0 = max(row - 1, 0), max(col - 1, 0)
    row1, col1 = min(row + 2, src.height), min(col + 2, src.width)
    window = rasterio.windows.Window(col0, row0, col1 - col0, row1 - row0)
    patch = src.read(1, window=window).astype("float64")

    nodata = src.nodata
    if nodata is not None:
        patch = np.where(patch == nodata, np.nan, patch)

    centre = patch[row - row0, col - col0]
    if np.isnan(centre):
        return empty

    elevation = float(centre)
    if patch.shape != (3, 3) or np.isnan(patch).any():
        # Edge or partially-nodata neighbourhood: elevation only.
        return {"elevation": elevation, "slope": None, "aspect": None}

    # Pixel size in metres. The DEM is geographic, so degrees are converted at
    # this latitude; a projected DEM is used as-is.
    res_x, res_y = abs(src.res[0]), abs(src.res[1])
    if src.crs is not None and src.crs.is_geographic:
        metres_per_degree = 111_320.0
        res_x *= metres_per_degree * math.cos(math.radians(y))
        res_y *= metres_per_degree

    a, b, c = patch[0]
    d, _, f = patch[1]
    g, h, i = patch[2]
    dz_dx = ((c + 2 * f + i) - (a + 2 * d + g)) / (8 * res_x)
    dz_dy = ((g + 2 * h + i) - (a + 2 * b + c)) / (8 * res_y)

    slope = math.degrees(math.atan(math.hypot(dz_dx, dz_dy)))
    aspect = math.degrees(math.atan2(dz_dy, -dz_dx))
    aspect = (450.0 - aspect) % 360.0 if slope > 0 else -1.0

    return {"elevation": elevation, "slope": slope, "aspect": aspect}


def extract_features_at_point(
    lon: float,
    lat: float,
    s2_path: Path | str | None = None,
    dem_path: Path | str | None = None,
) -> dict[str, float | None] | None:
    """Extract band reflectance and terrain attributes at one WGS84 point.

    Returns None when the point falls outside the Sentinel-2 footprint.
    Individual values are None where the raster has nodata there.
    """
    result = extract_features_bulk(
        pd.DataFrame([{"lon": lon, "lat": lat}]),
        s2_path=s2_path,
        dem_path=dem_path,
    )
    row = result.iloc[0]
    if all(row.get(column) is None or pd.isna(row.get(column)) for column in BAND_FEATURES):
        return None
    return {column: (None if pd.isna(row[column]) else float(row[column])) for column in FEATURE_COLUMNS}


def extract_features_bulk(
    points_df: pd.DataFrame,
    s2_path: Path | str | None = None,
    dem_path: Path | str | None = None,
    lon_col: str = "lon",
    lat_col: str = "lat",
) -> pd.DataFrame:
    """Extract features for many points from each raster's pooled handle.

    Returns `points_df` with the feature columns appended. Points outside a
    raster get NaN for that raster's columns.
    """
    s2 = Path(s2_path) if s2_path is not None else settings.s2_smoke_test
    dem = Path(dem_path) if dem_path is not None else settings.dem_smoke_test

    out = points_df.copy().reset_index(drop=True)
    lons = out[lon_col].astype(float).tolist()
    lats = out[lat_col].astype(float).tolist()

    band_rows: list[dict[str, Any]] = []
    src = raster_pool.dataset(s2)
    xs, ys = raster_pool.transformer("EPSG:4326", src.crs).transform(lons, lats)
    left, bottom, right, top = src.bounds
    inside = [left <= x <= right and bottom <= y <= top for x, y in zip(xs, ys, strict=True)]
    sampled = _sample_bands(src, list(xs), list(ys))
    for is_inside, row in zip(inside, sampled, strict=True):
        band_rows.append(row if is_inside else dict.fromkeys(BAND_COLUMNS.values()))

    terrain_rows: list[dict[str, float | None]] = []
    src = raster_pool.dataset(dem)
    dxs, dys = raster_pool.transformer("EPSG:4326", src.crs).transform(lons, lats)
    for x, y in zip(dxs, dys, strict=True):
        terrain_rows.append(_terrain_at(src, float(x), float(y)))

    features = pd.concat(
        [pd.DataFrame(band_rows), pd.DataFrame(terrain_rows)], axis=1
    ).reindex(columns=FEATURE_COLUMNS)

    return pd.concat([out, features], axis=1)
