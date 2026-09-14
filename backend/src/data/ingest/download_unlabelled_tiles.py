"""
Download 50 Sentinel-2 L2A tiles for autoencoder pretraining.

Sampling strategy:
  - 30 tiles across India (mineral belts + varied geology)
  - 15 tiles across Australia (foreign analogues we already have labels for)
  - 5 tiles across Brazil (Serra do Navio region)

Each tile is downloaded at 60m resolution (Sentinel-2's coarsest native
resolution) to keep storage manageable.

Uses Element84's public STAC catalog with windowed COG reads, so only the
~33x33 km box around each point is fetched rather than the full scene.

Run: python -m src.data.ingest.download_unlabelled_tiles
"""

from __future__ import annotations

import time
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

warnings.filterwarnings("ignore")

STAC_URL = "https://earth-search.aws.element84.com/v1"
COLLECTION = "sentinel-2-l2a"
DATE_RANGE = "2024-10-01/2025-03-31"  # dry-season window
MAX_CLOUD_PCT = 20.0

#: Half-width of each tile in degrees (~33 km across).
HALF_DEG = 0.15
TARGET_RES_M = 60.0

#: STAC asset keys for B02, B03, B04, B08, B11, B12 in that order.
ASSET_KEYS: list[str] = ["blue", "green", "red", "nir", "swir16", "swir22"]
BAND_NAMES: list[str] = ["B02", "B03", "B04", "B08", "B11", "B12"]

OUT_DIR: Path = settings.DATA_RAW / "satellite" / "unlabelled"

#: (name, lat, lon) sampling locations.
INDIA_TILES: list[tuple[str, float, float]] = [
    ("Balaghat_1", 21.8, 80.2),
    ("Balaghat_2", 21.5, 80.4),
    ("Nagpur_1", 21.15, 79.09),
    ("Bhandara_1", 21.17, 79.65),
    ("Sandur_1", 15.09, 76.55),
    ("Sandur_2", 15.15, 76.60),
    ("Chikla_1", 20.9, 80.0),
    ("Ukwa_1", 21.7, 80.1),
    ("Vishakapatnam_1", 17.68, 83.21),
    ("Vizag_2", 18.10, 83.40),
    ("Keonjhar_1", 21.63, 85.58),
    ("Keonjhar_2", 21.85, 85.35),
    ("Bonai_1", 21.83, 85.17),
    ("Sundargarh_1", 22.11, 84.03),
    ("Goa_1", 15.30, 74.10),
    ("MP_Betul", 21.90, 77.90),
    ("Rajasthan_1", 24.5, 74.5),
    ("Gujarat_1", 22.5, 71.0),
    ("Kutch_1", 23.20, 68.90),
    ("Karnataka_1", 12.97, 77.59),
    ("AP_Chittoor", 13.65, 79.42),
    ("TN_Salem", 11.66, 78.15),
    ("Kerala_1", 10.85, 76.27),
    ("Telangana_1", 17.38, 78.48),
    ("Chhattisgarh_1", 21.25, 81.62),
    ("Jharkhand_1", 23.35, 85.33),
    ("WB_1", 22.57, 88.36),
    ("Odisha_1", 20.27, 85.83),
    ("UP_1", 26.85, 80.94),
    ("Bihar_1", 25.61, 85.14),
]

AUSTRALIA_TILES: list[tuple[str, float, float]] = [
    ("Groote_1", -13.95, 136.60),
    ("Groote_2", -14.10, 136.75),
    ("Pilbara_1", -21.60, 118.90),
    ("Pilbara_2", -22.30, 119.50),
    ("Pilbara_3", -21.90, 118.20),
    ("Woodie_1", -22.70, 121.80),
    ("Woodie_2", -22.85, 121.65),
    ("NT_1", -14.50, 132.30),
    ("QLD_Fe_1", -22.60, 138.00),
    ("WA_1", -26.10, 118.00),
    ("SA_1", -32.60, 137.30),
    ("VIC_1", -37.50, 143.90),
    ("Kimberley_1", -16.80, 128.70),
    ("Tanami_1", -19.20, 129.60),
    ("Cloncurry_1", -20.71, 140.51),
]

BRAZIL_TILES: list[tuple[str, float, float]] = [
    ("Amapa_1", 0.90, -52.00),
    ("Amapa_2", 1.10, -52.20),
    ("Carajas_1", -6.10, -50.20),
    ("Carajas_2", -6.30, -50.40),
    ("MG_1", -19.50, -43.30),
]

ALL_TILES: list[tuple[str, float, float]] = INDIA_TILES + AUSTRALIA_TILES + BRAZIL_TILES


def _with_retry(fn, attempts: int = 4, base_delay: float = 4.0):
    """Run `fn`, retrying on transient network errors with exponential backoff.

    The STAC API and the COG reads both go over the public internet; a dropped
    DNS lookup mid-run should cost seconds, not the whole batch.
    """
    last: Exception | None = None
    for attempt in range(attempts):
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001 - retry any transient transport error
            last = exc
            if attempt == attempts - 1:
                break
            time.sleep(base_delay * (2**attempt))
    raise last  # type: ignore[misc]


def _bbox_for(lat: float, lon: float) -> list[float]:
    """WGS84 bbox of +/- HALF_DEG around a point."""
    return [lon - HALF_DEG, lat - HALF_DEG, lon + HALF_DEG, lat + HALF_DEG]


def _best_scene(
    client: Client,
    bbox: list[float],
    max_cloud: float = MAX_CLOUD_PCT,
    date_range: str = DATE_RANGE,
) -> dict | None:
    """Lowest-cloud scene in the date window, or None if nothing qualifies."""
    search = client.search(
        collections=[COLLECTION],
        bbox=bbox,
        datetime=date_range,
        query={"eo:cloud_cover": {"lt": max_cloud}},
        limit=100,
    )
    items = _with_retry(lambda: list(search.items()))
    if not items:
        return None
    best = min(items, key=lambda it: it.properties.get("eo:cloud_cover", 100.0))
    return {
        "item": best,
        "cloud": float(best.properties.get("eo:cloud_cover", float("nan"))),
        "date": str(best.datetime.date()) if best.datetime else "unknown",
        "id": best.id,
    }


def download_tile(
    client: Client,
    name: str,
    lat: float,
    lon: float,
    max_cloud: float = MAX_CLOUD_PCT,
    date_range: str = DATE_RANGE,
) -> dict | None:
    """Fetch one 6-band 60 m tile. Returns metadata, or None if unavailable."""
    out_path = OUT_DIR / f"{name}.tif"
    if out_path.exists():
        with rasterio.open(out_path) as src:
            return {
                "name": name,
                "skipped": True,
                "cloud": float(src.tags().get("cloud_cover", "nan")),
                "size_mb": out_path.stat().st_size / 1e6,
                "shape": src.shape,
            }

    bbox = _bbox_for(lat, lon)
    scene = _best_scene(client, bbox, max_cloud=max_cloud, date_range=date_range)
    if scene is None:
        return None

    item = scene["item"]

    # Build the destination grid in the scene's own UTM CRS at 60 m.
    with rasterio.open(item.assets[ASSET_KEYS[0]].href) as ref:
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
    for band_index, asset_key in enumerate(ASSET_KEYS):
        href = item.assets[asset_key].href
        with rasterio.open(href) as src:
            window = from_bounds(left, bottom, right, top, transform=src.transform)
            # Resampling.average downsamples 10 m / 20 m natives to the 60 m grid.
            data = src.read(
                1,
                window=window,
                out_shape=(height, width),
                resampling=Resampling.average,
                boundless=True,
                fill_value=0,
            )
        stack[band_index] = data.astype("uint16")

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
        dst.update_tags(
            cloud_cover=f"{scene['cloud']:.2f}",
            scene_id=scene["id"],
            scene_date=scene["date"],
            centre_lat=f"{lat}",
            centre_lon=f"{lon}",
        )

    return {
        "name": name,
        "skipped": False,
        "cloud": scene["cloud"],
        "size_mb": out_path.stat().st_size / 1e6,
        "shape": (height, width),
        "date": scene["date"],
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    client = Client.open(STAC_URL)

    results: list[dict] = []
    failures: list[str] = []

    for name, lat, lon in tqdm(ALL_TILES, desc="tiles", unit="tile"):
        try:
            info = _with_retry(lambda: download_tile(client, name, lat, lon), attempts=3)
            if info is None:
                failures.append(f"{name}: no scene under {MAX_CLOUD_PCT}% cloud in {DATE_RANGE}")
            else:
                results.append(info)
        except Exception as exc:  # noqa: BLE001 - one bad tile must not kill the run
            failures.append(f"{name}: {type(exc).__name__}: {exc}")

    downloaded = [r for r in results if not r["skipped"]]
    skipped = [r for r in results if r["skipped"]]
    total_mb = sum(r["size_mb"] for r in results)
    clouds = [r["cloud"] for r in results if not np.isnan(r["cloud"])]

    print("\n" + "=" * 60)
    print("UNLABELLED TILE DOWNLOAD")
    print("=" * 60)
    print(f"  requested      : {len(ALL_TILES)}")
    print(f"  downloaded     : {len(downloaded)}")
    print(f"  already present: {len(skipped)}")
    print(f"  failed         : {len(failures)}")
    print(f"  total size     : {total_mb:.1f} MB")
    if clouds:
        print(f"  avg cloud      : {np.mean(clouds):.2f}%  (min {min(clouds):.2f}, max {max(clouds):.2f})")
    print(f"  output dir     : {OUT_DIR}")
    if failures:
        print("\n  FAILURES:")
        for line in failures:
            print(f"    {line}")


if __name__ == "__main__":
    main()
