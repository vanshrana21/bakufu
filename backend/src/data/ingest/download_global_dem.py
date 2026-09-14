"""
Download Copernicus GLO-30 DEM coverage for every unlabelled Sentinel-2 tile.

Phases 2.5-2.8 had DEM coverage only over the Sausar smoke-test bbox, so every
foreign and most NGDR positives carried NaN (later -999) terrain while every
pseudo-negative carried real terrain. That made "terrain is missing" a near
perfect positive indicator. Giving every tile real terrain removes the
separator at its source.

One DEM raster is written per Sentinel-2 tile, clipped to that tile's bbox and
left in the DEM's native EPSG:4326 - the feature extractor reprojects points
per raster, so matching CRS is unnecessary.

Run: python -m src.data.ingest.download_global_dem
"""

from __future__ import annotations

import warnings
from pathlib import Path

import rasterio
from pystac_client import Client
from rasterio.merge import merge
from rasterio.warp import transform_bounds
from tqdm import tqdm

from src.config.settings import settings
from src.data.ingest.download_unlabelled_tiles import STAC_URL, _with_retry

warnings.filterwarnings("ignore")

DEM_COLLECTION = "cop-dem-glo-30"

TILE_DIR: Path = settings.DATA_RAW / "satellite" / "unlabelled"
OUT_DIR: Path = settings.DATA_RAW / "dem" / "global"

#: Small pad so points on a tile's edge still land inside the DEM window.
PAD_DEG: float = 0.02


def dem_path_for(tile_stem: str) -> Path:
    return OUT_DIR / f"dem_{tile_stem}.tif"


def tile_bbox(tile: Path) -> tuple[float, float, float, float]:
    """WGS84 bbox of a Sentinel-2 tile, padded slightly."""
    with rasterio.open(tile) as src:
        left, bottom, right, top = transform_bounds(src.crs, "EPSG:4326", *src.bounds)
    return (left - PAD_DEG, bottom - PAD_DEG, right + PAD_DEG, top + PAD_DEG)


def fetch_dem_for_tile(client: Client, tile: Path) -> dict | None:
    """Download and clip DEM coverage for one tile. None if unavailable."""
    out_path = dem_path_for(tile.stem)
    if out_path.exists():
        return {"tile": tile.stem, "skipped": True, "size_mb": out_path.stat().st_size / 1e6}

    bbox = tile_bbox(tile)
    search = client.search(collections=[DEM_COLLECTION], bbox=list(bbox), limit=100)
    items = _with_retry(lambda: list(search.items()))
    if not items:
        return None

    # The Copernicus DEM COGs sit in a public-but-S3-hosted bucket, so GDAL has
    # to be told to send unsigned requests rather than hunting for credentials.
    with rasterio.Env(AWS_NO_SIGN_REQUEST="YES", GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR"):
        sources = []
        try:
            for item in items:
                asset = item.assets.get("data")
                if asset:
                    sources.append(_with_retry(lambda a=asset: rasterio.open(a.href)))
            if not sources:
                return None

            mosaic, mosaic_transform = merge(sources, bounds=bbox)
            profile = sources[0].profile.copy()
            profile.update(
                {
                    "driver": "GTiff",
                    "height": mosaic.shape[1],
                    "width": mosaic.shape[2],
                    "transform": mosaic_transform,
                    "count": 1,
                    "compress": "deflate",
                    "tiled": True,
                }
            )
            out_path.parent.mkdir(parents=True, exist_ok=True)
            with rasterio.open(out_path, "w", **profile) as dst:
                dst.write(mosaic[0], 1)
        finally:
            for src in sources:
                src.close()

    return {
        "tile": tile.stem,
        "skipped": False,
        "size_mb": out_path.stat().st_size / 1e6,
        "dem_items": len(items),
    }


def _region_of(stem: str) -> str:
    if stem.startswith("foreign_"):
        return "foreign"
    if stem.startswith("ngdr_"):
        return "ngdr"
    return "phase2_pretrain"


def main() -> None:
    tiles = sorted(TILE_DIR.glob("*.tif"))
    if not tiles:
        raise FileNotFoundError(f"no Sentinel-2 tiles in {TILE_DIR}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    client = Client.open(STAC_URL)

    done: list[dict] = []
    missing: list[str] = []
    failed: list[str] = []

    for tile in tqdm(tiles, desc="DEM tiles", unit="tile"):
        try:
            info = fetch_dem_for_tile(client, tile)
            if info is None:
                missing.append(tile.stem)
            else:
                done.append({**info, "region": _region_of(tile.stem)})
        except Exception as exc:  # noqa: BLE001 - one bad tile must not kill the batch
            failed.append(f"{tile.stem}: {type(exc).__name__}: {exc}")

    per_region: dict[str, dict[str, float]] = {}
    for entry in done:
        stats = per_region.setdefault(str(entry["region"]), {"n": 0, "mb": 0.0})
        stats["n"] += 1
        stats["mb"] += float(entry["size_mb"])

    total_mb = sum(float(e["size_mb"]) for e in done)
    attempted = len(tiles)
    unavailable = len(missing) + len(failed)

    print("")
    print("=" * 68)
    print("GLOBAL COPERNICUS DEM DOWNLOAD")
    print("=" * 68)
    print("region".ljust(22) + "tiles".rjust(8) + "MB".rjust(12))
    print("-" * 68)
    for region, stats in sorted(per_region.items()):
        print(region.ljust(22) + str(int(stats["n"])).rjust(8) + f"{stats['mb']:.1f}".rjust(12))
    print("")
    print(f"  S2 tiles attempted   : {attempted}")
    print(f"  DEM obtained         : {len(done)} ({sum(1 for e in done if e['skipped'])} already present)")
    print(f"  no DEM coverage      : {len(missing)}")
    print(f"  failed               : {len(failed)}")
    print(f"  total size           : {total_mb:.1f} MB ({total_mb / 1024:.2f} GB)")
    print(f"  failure rate         : {unavailable / max(attempted, 1) * 100:.1f}%  (STOP threshold 30%)")
    print(f"  output dir           : {OUT_DIR}")
    if missing:
        print("")
        print("  NO DEM COVERAGE:")
        for stem in missing[:15]:
            print(f"    {stem}")
        if len(missing) > 15:
            print(f"    ... and {len(missing) - 15} more")
    if failed:
        print("")
        print("  FAILURES:")
        for line in failed[:15]:
            print(f"    {line}")
        if len(failed) > 15:
            print(f"    ... and {len(failed) - 15} more")


if __name__ == "__main__":
    main()
