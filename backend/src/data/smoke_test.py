"""
Smoke test — downloads Sentinel-2 imagery + Copernicus DEM tiles over the
Sausar manganese belt (Nagpur, MH + Balaghat, MP) and saves them locally.

Uses Element84's public STAC catalog — no Copernicus authentication
required. COG (Cloud-Optimized GeoTIFF) reads let us fetch only the
bbox we need instead of downloading full multi-hundred-MB scenes.

Run: python src/data/smoke_test.py
"""

from pathlib import Path
import sys
import warnings
warnings.filterwarnings("ignore")

import rasterio
from rasterio.merge import merge
from rasterio.transform import from_origin
from rasterio.warp import transform_bounds, Resampling
from rasterio.windows import from_bounds
import numpy as np
from pystac_client import Client

# Covers all 46 boreholes: lon 79.036-80.455, lat 21.409-21.975
BBOX = [79.0, 21.3, 80.6, 22.1]  # Sausar belt: Nagpur + Balaghat
DATE_RANGE = "2024-11-01/2025-02-28"  # dry season

# The bbox spans ~166 km E-W, wider than one 110 km MGRS tile, so several
# Sentinel-2 scenes are composited onto one explicit grid. All of 78-84E
# falls in UTM zone 44N, so the mosaic stays single-CRS.
DST_CRS = "EPSG:32644"
TARGET_RES = 20.0  # metres; 10 m over this bbox would be a ~1.7 GB raster

BANDS = ["blue", "green", "red", "nir", "swir16", "swir22"]  # B02,B03,B04,B08,B11,B12

# A single date per tile leaves holes where that scene was a partial swath, so
# fall back through the next-cleanest scenes until the tile's block is filled.
MAX_SCENES_PER_TILE = 3
FILL_TARGET = 0.995

REPO_ROOT = Path(__file__).resolve().parents[2]
S2_OUT = REPO_ROOT / "data" / "raw" / "satellite" / "s2_nagpur_smoke_test.tif"
DEM_OUT = REPO_ROOT / "data" / "raw" / "dem" / "dem_nagpur_smoke_test.tif"

STAC_URL = "https://earth-search.aws.element84.com/v1"


def build_grid():
    """Snapped destination grid in DST_CRS covering BBOX at TARGET_RES."""
    left, bottom, right, top = transform_bounds("EPSG:4326", DST_CRS, *BBOX)
    left = np.floor(left / TARGET_RES) * TARGET_RES
    bottom = np.floor(bottom / TARGET_RES) * TARGET_RES
    right = np.ceil(right / TARGET_RES) * TARGET_RES
    top = np.ceil(top / TARGET_RES) * TARGET_RES
    width = int(round((right - left) / TARGET_RES))
    height = int(round((top - bottom) / TARGET_RES))
    transform = from_origin(left, top, TARGET_RES, TARGET_RES)
    return transform, width, height, (left, bottom, right, top)


def composite_into(dst, src, grid_bounds):
    """Read the part of `src` overlapping the grid and paste it into `dst`.

    Zero is treated as nodata, so tiles fill each other's gaps instead of
    clobbering already-written pixels.
    """
    g_left, g_bottom, g_right, g_top = grid_bounds
    sb = src.bounds
    left, right = max(sb.left, g_left), min(sb.right, g_right)
    bottom, top = max(sb.bottom, g_bottom), min(sb.top, g_top)
    if right <= left or top <= bottom:
        return None

    col0 = int(round((left - g_left) / TARGET_RES))
    col1 = int(round((right - g_left) / TARGET_RES))
    row0 = int(round((g_top - top) / TARGET_RES))
    row1 = int(round((g_top - bottom) / TARGET_RES))
    out_h, out_w = row1 - row0, col1 - col0
    if out_h <= 0 or out_w <= 0:
        return None

    # Exact map bounds of that destination block, so the read aligns to the grid.
    b_left = g_left + col0 * TARGET_RES
    b_right = g_left + col1 * TARGET_RES
    b_top = g_top - row0 * TARGET_RES
    b_bottom = g_top - row1 * TARGET_RES

    window = from_bounds(b_left, b_bottom, b_right, b_top, transform=src.transform)
    data = src.read(
        1, window=window, out_shape=(out_h, out_w),
        resampling=Resampling.bilinear, boundless=True, fill_value=0,
    )
    block = dst[row0:row1, col0:col1]
    merged = np.where(block == 0, data, block)
    dst[row0:row1, col0:col1] = merged
    return float((merged != 0).mean())  # fill fraction of this tile's block


def fetch_sentinel2():
    print(f"\n[1/2] Querying Sentinel-2 L2A over the Sausar belt...")
    if S2_OUT.exists() and "--force" not in sys.argv:
        size_mb = S2_OUT.stat().st_size / 1024 / 1024
        print(f"    Reusing existing {S2_OUT.name} ({size_mb:.1f} MB) — pass --force to re-download")
        return "(cached)", "(cached)", float("nan"), 0

    client = Client.open(STAC_URL)
    search = client.search(
        collections=["sentinel-2-l2a"],
        bbox=BBOX,
        datetime=DATE_RANGE,
        query={"eo:cloud_cover": {"lt": 20}},
        limit=100,
    )
    items = list(search.items())
    if not items:
        raise RuntimeError("No Sentinel-2 scenes found. Try different dates.")

    # Cleanest few scenes per MGRS tile, so the whole bbox gets covered even
    # where the least-cloudy scene is only a partial swath.
    def cloud_of(item):
        return item.properties.get("eo:cloud_cover", 100)

    by_tile = {}
    for item in items:
        tile = item.properties.get("mgrs:tile") or item.id.split("_")[1]
        by_tile.setdefault(tile, []).append(item)
    for tile in by_tile:
        by_tile[tile] = sorted(by_tile[tile], key=cloud_of)[:MAX_SCENES_PER_TILE]

    tiles_sorted = sorted(by_tile, key=lambda t: cloud_of(by_tile[t][0]))
    print(f"    {len(items)} scenes found across {len(tiles_sorted)} MGRS tile(s); "
          f"up to {MAX_SCENES_PER_TILE} per tile")
    for tile in tiles_sorted:
        for item in by_tile[tile]:
            print(f"      {item.id}  {item.datetime.date()}  cloud {cloud_of(item):.1f}%")

    transform, width, height, grid_bounds = build_grid()
    print(f"    Grid: {width} x {height} px @ {TARGET_RES:.0f} m, {DST_CRS}")

    stacked = []
    for band_key in BANDS:
        dst = np.zeros((height, width), dtype="uint16")
        scenes_used = 0
        for tile in tiles_sorted:
            for item in by_tile[tile]:
                asset = item.assets.get(band_key)
                if not asset:
                    print(f"    WARN: band {band_key} missing on {item.id}, skipping")
                    continue
                with rasterio.open(asset.href) as src:
                    if str(src.crs) != DST_CRS:
                        print(f"    WARN: {item.id} is {src.crs}, not {DST_CRS} — skipping")
                        continue
                    block_fill = composite_into(dst, src, grid_bounds)
                if block_fill is None:
                    continue
                scenes_used += 1
                if block_fill >= FILL_TARGET:
                    break  # this tile's block is covered; skip its remaining dates
        filled = (dst != 0).mean() * 100
        print(f"    {band_key}: {scenes_used} scene(s), {filled:.1f}% filled")
        stacked.append(dst)

    S2_OUT.parent.mkdir(parents=True, exist_ok=True)
    profile = {
        "driver": "GTiff", "dtype": "uint16", "crs": DST_CRS,
        "transform": transform, "width": width, "height": height,
        "count": len(stacked), "compress": "deflate", "tiled": True,
    }
    with rasterio.open(S2_OUT, "w", **profile) as out:
        for i, band in enumerate(stacked, start=1):
            out.write(band, i)
        out.descriptions = tuple(BANDS)
    size_mb = S2_OUT.stat().st_size / 1024 / 1024
    print(f"    Saved: {S2_OUT} ({size_mb:.1f} MB)")

    best = by_tile[tiles_sorted[0]][0]
    return best.id, best.datetime.date(), cloud_of(best), len(tiles_sorted)


def fetch_dem():
    print(f"\n[2/2] Querying Copernicus DEM 30m over same bbox...")
    if DEM_OUT.exists() and "--force" not in sys.argv:
        size_mb = DEM_OUT.stat().st_size / 1024 / 1024
        print(f"    Reusing existing {DEM_OUT.name} ({size_mb:.1f} MB) — pass --force to re-download")
        return

    client = Client.open(STAC_URL)
    search = client.search(collections=["cop-dem-glo-30"], bbox=BBOX, limit=100)
    items = list(search.items())
    if not items:
        raise RuntimeError("No DEM tiles found.")
    print(f"    Found {len(items)} DEM tile(s)")

    # The Copernicus DEM COGs live in a public-but-S3-hosted bucket, so GDAL has
    # to be told to send unsigned requests rather than hunting for credentials.
    with rasterio.Env(AWS_NO_SIGN_REQUEST="YES", GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR"):
        tiles = []
        for item in items:
            asset = item.assets.get("data")
            if not asset:
                continue
            print(f"    Reading {item.id}...")
            src = rasterio.open(asset.href)
            tiles.append(src)

        # Copernicus DEM is EPSG:4326, so BBOX in degrees is the right unit here.
        mosaic, mosaic_transform = merge(tiles, bounds=BBOX)
        profile = tiles[0].profile.copy()
        profile.update({
            "driver": "GTiff",
            "height": mosaic.shape[1],
            "width": mosaic.shape[2],
            "transform": mosaic_transform,
            "count": 1,
            "compress": "deflate",
        })

        DEM_OUT.parent.mkdir(parents=True, exist_ok=True)
        with rasterio.open(DEM_OUT, "w", **profile) as dst:
            dst.write(mosaic[0], 1)
        for src in tiles:
            src.close()

    size_mb = DEM_OUT.stat().st_size / 1024 / 1024
    print(f"    Saved: {DEM_OUT} ({size_mb:.1f} MB)")


def main():
    print("=" * 60)
    print("SMOKE TEST — Sentinel-2 + Copernicus DEM over the Sausar belt")
    print("=" * 60)
    s2_id, s2_date, s2_cloud, n_tiles = fetch_sentinel2()
    fetch_dem()
    print("\n" + "=" * 60)
    print("DOWNLOAD COMPLETE")
    print("=" * 60)
    if n_tiles:
        print(f"Sentinel-2: {s2_id} (+{n_tiles - 1} more tile(s) composited)")
        print(f"Date: {s2_date}, Cloud cover: {s2_cloud:.1f}%")
    else:
        print(f"Sentinel-2: reused cached {S2_OUT.name}")
    print(f"Next step: run notebooks/02_smoke_test.ipynb for verification")


if __name__ == "__main__":
    main()
