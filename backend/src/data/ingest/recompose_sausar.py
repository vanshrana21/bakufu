"""
Re-compose the Sausar-belt Sentinel-2 mosaic with wider tile search,
longer date window, and slightly higher cloud cover, targeting <5% nodata.

Original mosaic: 25.67% nodata across bbox [79.0, 21.3, 80.6, 22.1].
Target: <5% nodata.

Reuses smoke_test's build_grid/composite_into unchanged; only the search
parameters are widened. smoke_test.py itself is imported, never modified.

Run: python -m src.data.ingest.recompose_sausar
"""

from __future__ import annotations

import warnings

import numpy as np
import rasterio
from pystac_client import Client

from src.config.settings import settings
from src.data.smoke_test import (
    BANDS,
    DST_CRS,
    FILL_TARGET,
    STAC_URL,
    TARGET_RES,
    build_grid,
    composite_into,
)

warnings.filterwarnings("ignore")

BBOX = [79.0, 21.3, 80.6, 22.1]  # same as smoke_test.py
DATE_RANGE = "2024-09-01/2025-04-30"  # widened from Nov-Feb -> Sep-Apr
CLOUD_CEILING = 35  # widened from 20 -> 35
MAX_SCENES_PER_TILE = 6  # widened from 3

OUT_PATH = settings.DATA_RAW / "satellite" / "s2_sausar_v2.tif"


def _cloud_of(item) -> float:
    return float(item.properties.get("eo:cloud_cover", 100.0))


def recompose() -> dict[str, object]:
    client = Client.open(STAC_URL)
    search = client.search(
        collections=["sentinel-2-l2a"],
        bbox=BBOX,
        datetime=DATE_RANGE,
        query={"eo:cloud_cover": {"lt": CLOUD_CEILING}},
        # Element84 caps page size at 100 and 500s on anything larger;
        # pystac-client paginates, so the full result set still arrives.
        limit=100,
        max_items=500,
    )
    items = list(search.items())
    if not items:
        raise RuntimeError("No Sentinel-2 scenes found for the widened window.")

    by_tile: dict[str, list] = {}
    for item in items:
        tile = item.properties.get("mgrs:tile") or item.id.split("_")[1]
        by_tile.setdefault(tile, []).append(item)
    for tile in by_tile:
        by_tile[tile] = sorted(by_tile[tile], key=_cloud_of)[:MAX_SCENES_PER_TILE]

    tiles_sorted = sorted(by_tile, key=lambda t: _cloud_of(by_tile[t][0]))
    print(f"  {len(items)} scenes found across {len(tiles_sorted)} MGRS tile(s)")
    print(f"  window {DATE_RANGE}, cloud < {CLOUD_CEILING}%, up to {MAX_SCENES_PER_TILE}/tile")
    for tile in tiles_sorted:
        clouds = ", ".join(f"{_cloud_of(i):.0f}%" for i in by_tile[tile])
        print(f"    {tile}: {len(by_tile[tile])} scene(s)  cloud {clouds}")

    transform, width, height, grid_bounds = build_grid()
    print(f"  grid: {width} x {height} px @ {TARGET_RES:.0f} m, {DST_CRS}")

    stacked: list[np.ndarray] = []
    scenes_used_total = 0
    skipped_crs: set[str] = set()

    for band_key in BANDS:
        dst = np.zeros((height, width), dtype="uint16")
        scenes_used = 0
        for tile in tiles_sorted:
            for item in by_tile[tile]:
                asset = item.assets.get(band_key)
                if not asset:
                    continue
                with rasterio.open(asset.href) as src:
                    if str(src.crs) != DST_CRS:
                        # Off-zone scenes are dropped, exactly as smoke_test does.
                        # Counted here so a CRS-driven gap is visible rather than silent.
                        skipped_crs.add(f"{item.id}:{src.crs}")
                        continue
                    block_fill = composite_into(dst, src, grid_bounds)
                if block_fill is None:
                    continue
                scenes_used += 1
                if block_fill >= FILL_TARGET:
                    break
        filled = (dst != 0).mean() * 100
        print(f"    {band_key}: {scenes_used} scene(s), {filled:.2f}% filled")
        scenes_used_total += scenes_used
        stacked.append(dst)

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    profile = {
        "driver": "GTiff",
        "dtype": "uint16",
        "crs": DST_CRS,
        "transform": transform,
        "width": width,
        "height": height,
        "count": len(stacked),
        "nodata": 0,
        "compress": "deflate",
        "tiled": True,
    }
    with rasterio.open(OUT_PATH, "w", **profile) as out:
        for i, band in enumerate(stacked, start=1):
            out.write(band, i)
        out.descriptions = tuple(BANDS)

    nodata_pct = float((stacked[0] == 0).mean() * 100)
    size_mb = OUT_PATH.stat().st_size / 1e6

    print("\n" + "=" * 60)
    print("SAUSAR RE-COMPOSITION")
    print("=" * 60)
    print(f"  scenes composited : {scenes_used_total} band-reads across {len(tiles_sorted)} MGRS tiles")
    print(f"  skipped (wrong CRS): {len(skipped_crs)}")
    for entry in sorted(skipped_crs):
        print(f"      {entry}")
    print(f"  old nodata        : 25.67%")
    print(f"  new nodata        : {nodata_pct:.2f}%")
    print(f"  target <5%        : {'PASS' if nodata_pct < 5.0 else 'FAIL'}")
    print(f"  output            : {OUT_PATH}  ({size_mb:.1f} MB)")

    return {
        "nodata_pct": nodata_pct,
        "scenes": scenes_used_total,
        "size_mb": size_mb,
        "mgrs_tiles": len(tiles_sorted),
        "skipped_crs": sorted(skipped_crs),
        "path": str(OUT_PATH),
    }


def main() -> None:
    recompose()


if __name__ == "__main__":
    main()
