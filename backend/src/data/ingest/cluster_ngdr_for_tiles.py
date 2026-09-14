"""
Cluster all 622 NGDR national records geographically. Determine which
clusters fall inside s2_sausar_v2.tif's existing bbox (skip those) and
which need new Sentinel-2 tile downloads.

Run: python -m src.data.ingest.cluster_ngdr_for_tiles
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
from rasterio.warp import transform_bounds
from sklearn.cluster import DBSCAN
from sqlalchemy import text

from src.config.settings import settings
from src.db.session import get_engine

SAUSAR_V2: Path = settings.DATA_RAW / "satellite" / "s2_sausar_v2.tif"
PLAN_PATH: Path = settings.DATA_PROCESSED / "ngdr_tile_plan.json"

DBSCAN_EPS_DEG: float = 0.15  # ~17 km
DBSCAN_MIN_SAMPLES: int = 3
SMALL_STATE_THRESHOLD: int = 5
MAX_NEW_TILES: int = 60

#: Half-width of a downloaded tile, matching the Phase 2.5 cluster tiles.
HALF_DEG: float = 0.15


def _slug(text_value: object) -> str:
    """Filesystem-safe state fragment."""
    return "".join(c if c.isalnum() else "_" for c in str(text_value)).strip("_").lower()[:24]


def load_ngdr() -> pd.DataFrame:
    """All NGDR national records with WGS84 coordinates."""
    sql = """
        SELECT id AS ngdr_id, source_layer, source_geometry_type, deposit_type,
               state,
               ST_Y(geom::geometry) AS lat, ST_X(geom::geometry) AS lon,
               ST_SRID(geom::geometry) AS srid
        FROM ngdr_national
    """
    with get_engine().connect() as conn:
        rows = conn.execute(text(sql)).all()
    frame = pd.DataFrame(
        rows,
        columns=[
            "ngdr_id", "source_layer", "source_geometry_type", "deposit_type",
            "state", "lat", "lon", "srid",
        ],
    )
    return frame


def sausar_bbox() -> tuple[float, float, float, float]:
    """WGS84 bounds of the re-composed Sausar mosaic."""
    with rasterio.open(SAUSAR_V2) as src:
        return transform_bounds(src.crs, "EPSG:4326", *src.bounds)


def build_plan() -> dict[str, object]:
    frame = load_ngdr()
    print(f"NGDR records loaded : {len(frame)}")

    srids = set(frame.srid.dropna().unique())
    print(f"geometry SRIDs      : {sorted(srids)} (4326 = WGS84)")
    frame = frame.dropna(subset=["lat", "lon"]).reset_index(drop=True)

    left, bottom, right, top = sausar_bbox()
    print(f"Sausar bbox         : lon {left:.4f}..{right:.4f}  lat {bottom:.4f}..{top:.4f}")

    covered_mask = (
        (frame.lon >= left) & (frame.lon <= right)
        & (frame.lat >= bottom) & (frame.lat <= top)
    )
    frame["covered_by_sausar"] = covered_mask
    outside = frame[~covered_mask].copy()
    print(f"already covered     : {int(covered_mask.sum())}")
    print(f"outside Sausar bbox : {len(outside)}")

    candidates: list[dict[str, object]] = []
    for state, group in outside.groupby(outside.state.fillna("UNKNOWN")):
        coords = group[["lat", "lon"]].to_numpy()
        if len(group) >= SMALL_STATE_THRESHOLD:
            labels = DBSCAN(eps=DBSCAN_EPS_DEG, min_samples=DBSCAN_MIN_SAMPLES).fit_predict(coords)
            for cluster_id in sorted(set(labels) - {-1}):
                member = coords[labels == cluster_id]
                candidates.append(
                    {
                        "state": str(state),
                        "kind": "cluster",
                        "centroid_lat": float(member[:, 0].mean()),
                        "centroid_lon": float(member[:, 1].mean()),
                        "n_records": int(len(member)),
                    }
                )
            # DBSCAN noise points in a large state still deserve a tile each,
            # budget permitting - they are real records, just isolated.
            for lat, lon in coords[labels == -1]:
                candidates.append(
                    {
                        "state": str(state),
                        "kind": "noise_singleton",
                        "centroid_lat": float(lat),
                        "centroid_lon": float(lon),
                        "n_records": 1,
                    }
                )
        else:
            for lat, lon in coords:
                candidates.append(
                    {
                        "state": str(state),
                        "kind": "singleton",
                        "centroid_lat": float(lat),
                        "centroid_lon": float(lon),
                        "n_records": 1,
                    }
                )

    # Densest clusters first so the tile cap buys the most label coverage.
    candidates.sort(key=lambda c: (-int(c["n_records"]), str(c["state"])))
    selected = candidates[:MAX_NEW_TILES]
    per_state_seq: dict[str, int] = {}
    for entry in selected:
        state_slug = _slug(entry["state"])
        per_state_seq[state_slug] = per_state_seq.get(state_slug, 0) + 1
        entry["tile_name"] = f"ngdr_{state_slug}_c{per_state_seq[state_slug]}"

    # How many outside-records the selected tiles actually reach.
    lat = outside.lat.to_numpy()
    lon = outside.lon.to_numpy()
    reached = np.zeros(len(outside), dtype=bool)
    for entry in selected:
        reached |= (
            (np.abs(lat - float(entry["centroid_lat"])) <= HALF_DEG)
            & (np.abs(lon - float(entry["centroid_lon"])) <= HALF_DEG)
        )
    still_uncovered = int((~reached).sum())

    plan = {
        "already_covered": int(covered_mask.sum()),
        "new_clusters": selected,
        "total_new_tiles": len(selected),
        "records_still_uncovered": still_uncovered,
        "candidates_dropped_by_cap": len(candidates) - len(selected),
        "sausar_bbox": [left, bottom, right, top],
    }

    PLAN_PATH.parent.mkdir(parents=True, exist_ok=True)
    PLAN_PATH.write_text(json.dumps(plan, indent=2), encoding="utf-8")

    print("")
    print("=" * 72)
    print("NGDR TILE PLAN")
    print("=" * 72)
    print("state".ljust(26) + "in-Sausar".rjust(11) + "clusters".rjust(10) + "reached".rjust(9))
    print("-" * 72)
    for state in sorted(set(frame.state.fillna("UNKNOWN"))):
        in_sausar = int(((frame.state.fillna("UNKNOWN") == state) & covered_mask).sum())
        n_clusters = sum(1 for c in selected if c["state"] == state)
        sub = outside.state.fillna("UNKNOWN") == state
        n_reached = int(reached[sub.to_numpy()].sum()) if sub.any() else 0
        print(str(state)[:26].ljust(26) + str(in_sausar).rjust(11) + str(n_clusters).rjust(10) + str(n_reached).rjust(9))

    print("")
    print(f"  already covered by Sausar : {plan['already_covered']}")
    print(f"  new tiles planned         : {plan['total_new_tiles']} (cap {MAX_NEW_TILES}, dropped {plan['candidates_dropped_by_cap']})")
    print(f"  records still uncovered   : {plan['records_still_uncovered']}")
    print(f"  plan written to           : {PLAN_PATH}")
    return plan


def main() -> None:
    build_plan()


if __name__ == "__main__":
    main()
