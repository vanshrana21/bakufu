"""
Fetch Precambrian formation polygons over the Sausar belt from Macrostrat.

PLACEHOLDER SOURCE. Macrostrat serves Chorlton's generalized world geology
(~1:5M), so boundaries are tens of kilometres coarse. It is good enough to
separate Precambrian basement from Deccan Trap basalt and alluvium, and not
good enough to resolve a field boundary. Production should replace this with
GSI Bhukosh 1:50K polygons - the downstream mask interface does not change.

Macrostrat has no bbox endpoint for map units, so the bbox is sampled on a
grid and the returned polygons are de-duplicated by map_id.

Run: python -m src.data.ingest.fetch_macrostrat_geology
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import geopandas as gpd
import numpy as np
import requests
from shapely.geometry import shape
from tqdm import tqdm

from src.config.settings import settings

API = "https://macrostrat.org/api/v2/geologic_units/map"

#: Sausar belt: Balaghat / Bhandara / Nagpur and adjacent districts.
BBOX = (79.0, 21.3, 80.6, 22.1)
GRID_STEP_DEG = 0.10  # ~11 km; finer than any boundary this source resolves

#: Base of the Cambrian. Anything older than this is Precambrian.
CAMBRIAN_BASE_MA = 541.0

OUT_PATH: Path = (
    settings.DATA_RAW / "india" / "geology" / "sausar_precambrian_formations_macrostrat_proxy.geojson"
)


def _query(lat: float, lon: float, session: requests.Session) -> list[dict]:
    """Map units at one point, with geometry. Empty list on any failure."""
    try:
        response = session.get(
            API,
            params={"lat": lat, "lng": lon, "format": "geojson"},
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
    except Exception:  # noqa: BLE001 - one dead sample must not kill the sweep
        return []
    data = payload.get("success", {}).get("data", {})
    return data.get("features", []) or []


def is_precambrian(properties: dict) -> bool:
    """True when the unit's young edge is older than the base of the Cambrian."""
    top = properties.get("t_age")
    if top is None:
        return False
    try:
        return float(top) >= CAMBRIAN_BASE_MA
    except (TypeError, ValueError):
        return False


def fetch(bbox: tuple[float, float, float, float] = BBOX, step: float = GRID_STEP_DEG) -> gpd.GeoDataFrame:
    left, bottom, right, top = bbox
    lons = np.arange(left, right + step / 2, step)
    lats = np.arange(bottom, top + step / 2, step)
    samples = [(float(la), float(lo)) for la in lats for lo in lons]

    session = requests.Session()
    by_map_id: dict[int, dict] = {}
    all_units: dict[int, dict] = {}
    misses = 0

    for lat, lon in tqdm(samples, desc="macrostrat", unit="pt"):
        features = _query(lat, lon, session)
        if not features:
            misses += 1
        for feature in features:
            properties = feature.get("properties", {})
            map_id = properties.get("map_id")
            if map_id is None:
                continue
            all_units[map_id] = properties
            if is_precambrian(properties) and feature.get("geometry"):
                by_map_id[map_id] = feature
        time.sleep(0.05)  # be polite to a free public API

    print("")
    print(f"  grid samples        : {len(samples)}  ({len(lons)} x {len(lats)} at {step} deg)")
    print(f"  samples with no unit: {misses}")
    print(f"  distinct map units  : {len(all_units)}")
    print(f"  Precambrian units   : {len(by_map_id)}")

    print("")
    print("  all units seen in bbox:")
    for map_id, properties in sorted(all_units.items(), key=lambda kv: -float(kv[1].get("t_age") or 0)):
        flag = "PRECAMBRIAN" if is_precambrian(properties) else "excluded  "
        print(
            f"    [{flag}] {str(properties.get('name'))[:52]:<52} "
            f"{properties.get('t_age')}-{properties.get('b_age')} Ma"
        )

    if not by_map_id:
        raise RuntimeError("no Precambrian polygons returned for the bbox")

    records = []
    geometries = []
    for map_id, feature in by_map_id.items():
        properties = feature["properties"]
        records.append(
            {
                "map_id": map_id,
                "formation_name": properties.get("name"),
                "strat_name": properties.get("strat_name") or None,
                "lithology": properties.get("lith"),
                "description": properties.get("descrip") or None,
                "age_top_name": properties.get("t_int_name"),
                "age_bottom_name": properties.get("b_int_name"),
                "t_age_ma": properties.get("t_age"),
                "b_age_ma": properties.get("b_age"),
                "source_id": properties.get("source_id"),
                "source": "macrostrat_chorlton_generalized_world_geology",
                "scale": "~1:5,000,000 (PLACEHOLDER - replace with GSI Bhukosh 1:50K)",
            }
        )
        geometries.append(shape(feature["geometry"]))

    gdf = gpd.GeoDataFrame(records, geometry=geometries, crs="EPSG:4326")
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    gdf.to_file(OUT_PATH, driver="GeoJSON")

    # How much of the study bbox the mask actually covers.
    from shapely.geometry import box

    study = box(*bbox)
    covered = gdf.geometry.union_all().intersection(study)
    coverage_pct = covered.area / study.area * 100.0

    print("")
    print("=" * 70)
    print("MACROSTRAT PRECAMBRIAN POLYGONS")
    print("=" * 70)
    print(f"  polygons saved     : {len(gdf)}")
    print(f"  bbox coverage      : {coverage_pct:.1f}% of {bbox}")
    print(f"  file               : {OUT_PATH}  ({OUT_PATH.stat().st_size / 1e6:.2f} MB)")
    print("")
    print("  formations:")
    for name, group in gdf.groupby("formation_name"):
        print(f"    {str(name)[:56]:<56} x{len(group)}")

    return gdf


def main() -> None:
    fetch()


if __name__ == "__main__":
    main()
