"""
Download Sentinel-2 tiles centred on NGDR cluster centroids identified
in Step 1. Same parameters as Phase 2.5's foreign cluster tiles.

Run: python -m src.data.ingest.download_ngdr_tiles
"""

from __future__ import annotations

import json
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from pystac_client import Client
from tqdm import tqdm

from src.config.settings import settings
from src.data.ingest.cluster_ngdr_for_tiles import HALF_DEG, PLAN_PATH, load_ngdr
from src.data.ingest.download_unlabelled_tiles import (
    OUT_DIR,
    STAC_URL,
    _with_retry,
    download_tile,
)

warnings.filterwarnings("ignore")

DATE_RANGE: str = "2024-09-01/2025-04-30"
CLOUD_PCT: float = 30.0
#: One widened retry before a cluster is abandoned.
CLOUD_PCT_RETRY: float = 45.0

MAX_TILES_GUARD: int = 60
MAX_GB_GUARD: float = 8.0


def main() -> None:
    if not PLAN_PATH.exists():
        raise FileNotFoundError(
            f"no tile plan at {PLAN_PATH} - run python -m src.data.ingest.cluster_ngdr_for_tiles"
        )
    plan = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
    clusters = plan["new_clusters"]

    if len(clusters) > MAX_TILES_GUARD:
        raise RuntimeError(
            f"plan asks for {len(clusters)} tiles, above the {MAX_TILES_GUARD} guard - stopping"
        )

    print(f"clusters to fetch : {len(clusters)}")
    print(f"window            : {DATE_RANGE}, cloud < {CLOUD_PCT}% (retry at {CLOUD_PCT_RETRY}%)")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    client = Client.open(STAC_URL)

    downloaded: list[dict[str, object]] = []
    skipped_existing: list[str] = []
    skipped_cloud: list[str] = []
    failures: list[str] = []

    for cluster in tqdm(clusters, desc="ngdr tiles", unit="tile"):
        name = str(cluster["tile_name"])
        lat = float(cluster["centroid_lat"])
        lon = float(cluster["centroid_lon"])
        try:
            info = _with_retry(
                lambda: download_tile(
                    client, name, lat, lon, max_cloud=CLOUD_PCT, date_range=DATE_RANGE
                ),
                attempts=3,
            )
            if info is None:
                # Widen the cloud ceiling once before giving up on this cluster.
                info = _with_retry(
                    lambda: download_tile(
                        client, name, lat, lon, max_cloud=CLOUD_PCT_RETRY, date_range=DATE_RANGE
                    ),
                    attempts=2,
                )
            if info is None:
                skipped_cloud.append(f"{name} ({cluster['state']}): no scene under {CLOUD_PCT_RETRY}% cloud")
                continue
            if info.get("skipped"):
                skipped_existing.append(name)
            downloaded.append({**cluster, **info})
        except Exception as exc:  # noqa: BLE001 - one bad tile must not kill the batch
            failures.append(f"{name}: {type(exc).__name__}: {exc}")

        total_gb = sum(float(d.get("size_mb", 0.0)) for d in downloaded) / 1000.0
        if total_gb > MAX_GB_GUARD:
            raise RuntimeError(f"downloaded {total_gb:.2f} GB, above the {MAX_GB_GUARD} GB guard - stopping")

    # How many NGDR records the freshly-downloaded tiles actually reach.
    ngdr = load_ngdr().dropna(subset=["lat", "lon"])
    lat = ngdr.lat.to_numpy()
    lon = ngdr.lon.to_numpy()
    reached = np.zeros(len(ngdr), dtype=bool)
    for entry in downloaded:
        reached |= (
            (np.abs(lat - float(entry["centroid_lat"])) <= HALF_DEG)
            & (np.abs(lon - float(entry["centroid_lon"])) <= HALF_DEG)
        )

    per_state: dict[str, dict[str, float]] = {}
    for cluster in clusters:
        stats = per_state.setdefault(str(cluster["state"]), {"attempted": 0, "got": 0, "mb": 0.0})
        stats["attempted"] += 1
    got_names = {str(d["tile_name"]) for d in downloaded}
    for entry in downloaded:
        stats = per_state[str(entry["state"])]
        stats["got"] += 1
        stats["mb"] += float(entry.get("size_mb", 0.0))

    total_mb = sum(float(d.get("size_mb", 0.0)) for d in downloaded)
    tiles_on_disk = len(list(OUT_DIR.glob("*.tif")))

    print("")
    print("=" * 72)
    print("NGDR TILE DOWNLOAD")
    print("=" * 72)
    print("state".ljust(30) + "attempted".rjust(11) + "got".rjust(7) + "MB".rjust(10))
    print("-" * 72)
    for state, stats in sorted(per_state.items(), key=lambda kv: -kv[1]["attempted"]):
        print(
            str(state)[:30].ljust(30)
            + str(int(stats["attempted"])).rjust(11)
            + str(int(stats["got"])).rjust(7)
            + f"{stats['mb']:.1f}".rjust(10)
        )

    print("")
    print(f"  tiles obtained        : {len(downloaded)} of {len(clusters)}")
    print(f"  already present       : {len(skipped_existing)}")
    print(f"  skipped (cloud)       : {len(skipped_cloud)}")
    print(f"  failed                : {len(failures)}")
    print(f"  total size            : {total_mb:.1f} MB ({total_mb / 1000:.2f} GB)")
    print(f"  tiles now in unlabelled/: {tiles_on_disk}")
    print(f"  NGDR records reached by new tiles: {int(reached.sum())} of {len(ngdr)}")
    if skipped_cloud:
        print("")
        print("  SKIPPED CLUSTERS:")
        for line in skipped_cloud:
            print(f"    {line}")
    if failures:
        print("")
        print("  FAILURES:")
        for line in failures[:15]:
            print(f"    {line}")


if __name__ == "__main__":
    main()
