"""
Re-fetch NGDR cluster tiles as multi-scene composites.

Phase 2.8 took the single lowest-cloud scene per cluster. Where that scene only
partly covered the +/-0.15 degree window the remainder was zero-filled, and 184
NGDR positives were dropped for landing on those gaps - one tile came back
96.8% nodata. This fills each window from up to 6 scenes, the same approach
that took the Sausar mosaic from 25.67% nodata to 0.00%.

Writes ngdr_{state}_c{n}_v2.tif alongside the originals; the Phase 2.8 tiles
are left untouched.

Run: python -m src.data.ingest.composite_ngdr_tiles
"""

from __future__ import annotations

import json
import warnings
from pathlib import Path

import numpy as np
import rasterio
from pystac_client import Client
from rasterio.enums import Resampling
from rasterio.transform import from_origin
from rasterio.warp import transform_bounds
from rasterio.windows import from_bounds
from tqdm import tqdm

from src.config.settings import settings
from src.data.ingest.download_unlabelled_tiles import (
    ASSET_KEYS,
    BAND_NAMES,
    HALF_DEG,
    OUT_DIR,
    STAC_URL,
    TARGET_RES_M,
    _with_retry,
)

warnings.filterwarnings("ignore")

DATE_RANGE: str = "2024-09-01/2025-04-30"
CLOUD_PCT: float = 35.0
MAX_SCENES_PER_TILE: int = 6
#: Stop pulling further scenes once the window is essentially full.
FILL_TARGET: float = 0.995

PLAN_PATH: Path = settings.DATA_PROCESSED / "ngdr_tile_plan.json"
REPORT_PATH: Path = settings.DATA_PROCESSED / "ngdr_composite_report.json"


def _cloud_of(item) -> float:
    return float(item.properties.get("eo:cloud_cover", 100.0))


def _nodata_fraction(path: Path) -> float | None:
    if not path.exists():
        return None
    with rasterio.open(path) as src:
        return float((src.read(1) == 0).mean())


def composite_tile(client: Client, name: str, lat: float, lon: float) -> dict | None:
    """Build one 6-band 60 m tile from up to MAX_SCENES_PER_TILE scenes."""
    out_path = OUT_DIR / f"{name}_v2.tif"
    original_nodata = _nodata_fraction(OUT_DIR / f"{name}.tif")

    if out_path.exists():
        return {
            "name": name,
            "skipped": True,
            "original_nodata": original_nodata,
            "new_nodata": _nodata_fraction(out_path),
            "scenes_used": None,
            "size_mb": out_path.stat().st_size / 1e6,
        }

    bbox = [lon - HALF_DEG, lat - HALF_DEG, lon + HALF_DEG, lat + HALF_DEG]
    search = client.search(
        collections=["sentinel-2-l2a"],
        bbox=bbox,
        datetime=DATE_RANGE,
        query={"eo:cloud_cover": {"lt": CLOUD_PCT}},
        limit=100,
    )
    items = _with_retry(lambda: list(search.items()))
    if not items:
        return None

    # Cleanest scenes first, so the best imagery wins each pixel and later
    # scenes only fill what is still empty.
    items = sorted(items, key=_cloud_of)[:MAX_SCENES_PER_TILE]

    with rasterio.open(items[0].assets[ASSET_KEYS[0]].href) as ref:
        dst_crs = ref.crs
    left, bottom, right, top = transform_bounds("EPSG:4326", dst_crs, *bbox)
    left = np.floor(left / TARGET_RES_M) * TARGET_RES_M
    bottom = np.floor(bottom / TARGET_RES_M) * TARGET_RES_M
    right = np.ceil(right / TARGET_RES_M) * TARGET_RES_M
    top = np.ceil(top / TARGET_RES_M) * TARGET_RES_M
    width = int(round((right - left) / TARGET_RES_M))
    height = int(round((top - bottom) / TARGET_RES_M))
    transform = from_origin(left, top, TARGET_RES_M, TARGET_RES_M)

    stack = np.zeros((len(ASSET_KEYS), height, width), dtype="uint16")
    scenes_used = 0

    for item in items:
        # Scenes from a neighbouring UTM zone cannot be pasted onto this grid.
        try:
            with rasterio.open(item.assets[ASSET_KEYS[0]].href) as probe:
                if probe.crs != dst_crs:
                    continue
        except Exception:  # noqa: BLE001 - unreadable scene, try the next
            continue

        contributed = False
        for band_index, asset_key in enumerate(ASSET_KEYS):
            asset = item.assets.get(asset_key)
            if asset is None:
                continue
            try:
                with rasterio.open(asset.href) as src:
                    window = from_bounds(left, bottom, right, top, transform=src.transform)
                    data = src.read(
                        1,
                        window=window,
                        out_shape=(height, width),
                        resampling=Resampling.average,
                        boundless=True,
                        fill_value=0,
                    ).astype("uint16")
            except Exception:  # noqa: BLE001 - skip an unreadable band
                continue
            # Zero is nodata, so already-filled pixels are preserved and this
            # scene only contributes where the mosaic is still empty.
            target = stack[band_index]
            np.copyto(target, data, where=(target == 0))
            contributed = True

        if contributed:
            scenes_used += 1
        if float((stack[0] != 0).mean()) >= FILL_TARGET:
            break

    if scenes_used == 0:
        return None

    profile = {
        "driver": "GTiff",
        "height": height,
        "width": width,
        "count": len(ASSET_KEYS),
        "dtype": "uint16",
        "crs": dst_crs,
        "transform": transform,
        "nodata": 0,
        "compress": "deflate",
        "tiled": True,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(out_path, "w", **profile) as dst:
        dst.write(stack)
        for i, band_name in enumerate(BAND_NAMES, start=1):
            dst.set_band_description(i, band_name)
        dst.update_tags(scenes_used=str(scenes_used), centre_lat=str(lat), centre_lon=str(lon))

    return {
        "name": name,
        "skipped": False,
        "original_nodata": original_nodata,
        "new_nodata": float((stack[0] == 0).mean()),
        "scenes_used": scenes_used,
        "size_mb": out_path.stat().st_size / 1e6,
    }


def main() -> None:
    plan = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
    clusters = plan["new_clusters"]
    client = Client.open(STAC_URL)

    results: list[dict] = []
    failures: list[str] = []

    for cluster in tqdm(clusters, desc="compositing", unit="tile"):
        name = str(cluster["tile_name"])
        try:
            info = _with_retry(
                lambda c=cluster, n=name: composite_tile(
                    client, n, float(c["centroid_lat"]), float(c["centroid_lon"])
                ),
                attempts=3,
            )
            if info is None:
                failures.append(f"{name}: no usable scene under {CLOUD_PCT}% cloud")
            else:
                results.append({**info, "state": cluster["state"]})
        except Exception as exc:  # noqa: BLE001 - one tile must not kill the batch
            failures.append(f"{name}: {type(exc).__name__}: {exc}")

    improved = [r for r in results if r["original_nodata"] is not None and r["new_nodata"] is not None]
    print("")
    print("=" * 76)
    print("NGDR TILE COMPOSITING")
    print("=" * 76)
    print("tile".ljust(34) + "scenes".rjust(8) + "old nodata".rjust(13) + "new nodata".rjust(13))
    print("-" * 76)
    for entry in sorted(improved, key=lambda e: -(e["original_nodata"] or 0))[:20]:
        scenes = entry["scenes_used"] if entry["scenes_used"] is not None else "-"
        print(
            str(entry["name"])[:34].ljust(34)
            + str(scenes).rjust(8)
            + f"{entry['original_nodata'] * 100:>12.2f}%"
            + f"{entry['new_nodata'] * 100:>12.2f}%"
        )

    total_mb = sum(float(r["size_mb"]) for r in results)
    if improved:
        old_mean = float(np.mean([e["original_nodata"] for e in improved]) * 100)
        new_mean = float(np.mean([e["new_nodata"] for e in improved]) * 100)
    else:
        old_mean = new_mean = float("nan")

    print("")
    print(f"  tiles composited : {len(results)} of {len(clusters)}")
    print(f"  failed           : {len(failures)}")
    print(f"  mean nodata      : {old_mean:.2f}%  ->  {new_mean:.2f}%")
    print(f"  total size       : {total_mb:.1f} MB")
    if failures:
        print("")
        print("  FAILURES:")
        for line in failures[:10]:
            print(f"    {line}")

    REPORT_PATH.write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
    print(f"  report written   : {REPORT_PATH}")


if __name__ == "__main__":
    main()
