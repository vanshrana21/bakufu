"""
Download unlabelled Sentinel-2 tiles centred on foreign deposit CLUSTERS
so that pretraining tiles actually cover foreign labels.

Original Phase 2: tiles at region centroids (Groote_1, Pilbara_1, etc.)
30km tiles rarely intersected the 1247 Australian deposits scattered
across the continent, yielding only 11 usable positives.

Fix: cluster deposit coordinates via DBSCAN, download one tile centred
on each cluster centroid.

Run: python -m src.data.ingest.download_foreign_cluster_tiles
"""

from __future__ import annotations

import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from pystac_client import Client
from sklearn.cluster import DBSCAN
from tqdm import tqdm

from src.config.settings import settings
from src.data.ingest.download_unlabelled_tiles import (
    HALF_DEG,
    OUT_DIR,
    STAC_URL,
    _with_retry,
    download_tile,
)

warnings.filterwarnings("ignore")

CSV_PATH: Path = settings.DATA_RAW / "foreign" / "foreign_manganese_deposits_20260826.csv"

DBSCAN_EPS_DEG: float = 0.15  # ~17 km
DBSCAN_MIN_SAMPLES: int = 3
MIN_CLUSTER_SIZE: int = 5
SMALL_COUNTRY_THRESHOLD: int = 5
MAX_NEW_TILES: int = 60
CLUSTER_CLOUD_PCT: float = 30.0  # relaxed from the 20% used for region tiles


def _slug(text: str) -> str:
    """Filesystem-safe country fragment."""
    return "".join(c if c.isalnum() else "_" for c in str(text)).strip("_")[:28]


def find_clusters(frame: pd.DataFrame) -> list[dict[str, object]]:
    """Cluster centroids worth a tile, largest first.

    Countries with >= SMALL_COUNTRY_THRESHOLD deposits are clustered with
    DBSCAN and only clusters of >= MIN_CLUSTER_SIZE earn a tile. Countries
    below that threshold contribute their deposits individually, since a
    handful of scattered points would never form a cluster.
    """
    candidates: list[dict[str, object]] = []

    for country, group in frame.groupby("country"):
        coords = group[["latitude", "longitude"]].to_numpy()

        if len(group) >= SMALL_COUNTRY_THRESHOLD:
            labels = DBSCAN(eps=DBSCAN_EPS_DEG, min_samples=DBSCAN_MIN_SAMPLES).fit_predict(coords)
            for cluster_id in sorted(set(labels) - {-1}):
                member = coords[labels == cluster_id]
                if len(member) < MIN_CLUSTER_SIZE:
                    continue
                candidates.append(
                    {
                        "country": country,
                        "kind": "cluster",
                        "lat": float(member[:, 0].mean()),
                        "lon": float(member[:, 1].mean()),
                        "size": int(len(member)),
                    }
                )
        else:
            for lat, lon in coords:
                candidates.append(
                    {
                        "country": country,
                        "kind": "singleton",
                        "lat": float(lat),
                        "lon": float(lon),
                        "size": 1,
                    }
                )

    # Biggest clusters first, so the tile cap buys the most label coverage.
    candidates.sort(key=lambda c: (-int(c["size"]), str(c["country"])))
    for index, candidate in enumerate(candidates):
        candidate["name"] = f"foreign_{_slug(candidate['country'])}_c{index:02d}"
    return candidates


def deposits_in_tiles(frame: pd.DataFrame, tiles: list[dict[str, object]]) -> int:
    """How many deposits fall inside at least one downloaded tile window."""
    lat = frame["latitude"].to_numpy()
    lon = frame["longitude"].to_numpy()
    covered = np.zeros(len(frame), dtype=bool)
    for tile in tiles:
        covered |= (
            (np.abs(lat - float(tile["lat"])) <= HALF_DEG)
            & (np.abs(lon - float(tile["lon"])) <= HALF_DEG)
        )
    return int(covered.sum())


def main() -> None:
    frame = pd.read_csv(CSV_PATH).dropna(subset=["latitude", "longitude"])
    print(f"foreign deposits with coordinates: {len(frame)}")

    candidates = find_clusters(frame)
    selected = candidates[:MAX_NEW_TILES]
    dropped = len(candidates) - len(selected)
    print(f"tile candidates: {len(candidates)}  ->  selected {len(selected)} (cap {MAX_NEW_TILES}, dropped {dropped})")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    client = Client.open(STAC_URL)

    downloaded: list[dict[str, object]] = []
    skipped: list[str] = []
    failures: list[str] = []

    for candidate in tqdm(selected, desc="foreign tiles", unit="tile"):
        try:
            info = _with_retry(
                lambda c=candidate: download_tile(
                    client, str(c["name"]), float(c["lat"]), float(c["lon"]),
                    max_cloud=CLUSTER_CLOUD_PCT,
                ),
                attempts=3,
            )
            if info is None:
                failures.append(f"{candidate['name']}: no scene under {CLUSTER_CLOUD_PCT}% cloud")
            elif info["skipped"]:
                skipped.append(str(candidate["name"]))
                downloaded.append({**candidate, **info})
            else:
                downloaded.append({**candidate, **info})
        except Exception as exc:  # noqa: BLE001 - one bad tile must not kill the batch
            failures.append(f"{candidate['name']}: {type(exc).__name__}: {exc}")

    print("\n" + "=" * 68)
    print("FOREIGN CLUSTER TILES")
    print("=" * 68)
    per_country: dict[str, dict[str, int]] = {}
    for candidate in selected:
        stats = per_country.setdefault(str(candidate["country"]), {"clusters": 0, "deposits": 0})
        stats["clusters"] += 1
        stats["deposits"] += int(candidate["size"])
    got = {str(d["name"]) for d in downloaded}
    print(f"{'country':<28}{'tiles':>7}{'got':>6}{'avg cluster':>13}")
    print("-" * 68)
    for country, stats in sorted(per_country.items(), key=lambda kv: -kv[1]["clusters"]):
        have = sum(1 for c in selected if str(c["country"]) == country and str(c["name"]) in got)
        avg = stats["deposits"] / stats["clusters"]
        print(f"{country:<28}{stats['clusters']:>7}{have:>6}{avg:>13.1f}")

    total_mb = sum(float(d.get("size_mb", 0.0)) for d in downloaded)
    in_tile = deposits_in_tiles(frame, downloaded)
    print(f"\n  tiles obtained  : {len(downloaded)} ({len(skipped)} already present)")
    print(f"  failed          : {len(failures)}")
    print(f"  total size      : {total_mb:.1f} MB")
    print(f"  deposits now in-tile (geometric estimate): {in_tile} of {len(frame)}")
    if failures:
        print("\n  FAILURES:")
        for line in failures[:15]:
            print(f"    {line}")
        if len(failures) > 15:
            print(f"    ... and {len(failures) - 15} more")


if __name__ == "__main__":
    main()
