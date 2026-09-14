"""
Known-occurrence buffer mask - union of per-point buffers around every
Indian manganese positive (boreholes + XRF + NGDR points), 5 km radius.

Scientifically literal: "predictions are constrained to ground within 5 km
of a confirmed manganese occurrence." A convex hull would not support that
sentence - it fills its own interior, so a point tens of kilometres from any
occurrence can still fall inside it. A union of per-point buffers is the
shape the claim actually describes.

Trade-off: excludes greenfield exploration, which is the point. On public
data alone this is the honest ceiling of what can be claimed.

Run: python -m src.data.masks.occurrence_buffer_mask
"""

from __future__ import annotations

import math
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point
from shapely.ops import unary_union
from shapely.prepared import prep
from sqlalchemy import text

from src.config.settings import settings
from src.db.session import get_engine

#: 5 km, not 10. At 10 km the Nagpur cropland false positive (7.21 km from
#: the nearest confirmed occurrence) survives; at 5 km it does not, while
#: every true positive stays inside.
BUFFER_KM: float = 5.0

#: Sausar study bbox, matching the mosaic the model scores against.
SAUSAR_BBOX = (79.0, 21.3, 80.6, 22.1)

OUT_PATH: Path = settings.DATA_RAW / "india" / "geology" / "occurrence_buffer_5km.geojson"


def _read(sql: str) -> pd.DataFrame:
    with get_engine().connect() as conn:
        rows = conn.execute(text(sql)).all()
    return pd.DataFrame(rows, columns=["lat", "lon"])


def build_occurrence_buffer_mask(
    buffer_km: float = BUFFER_KM,
    output_path: Path | None = None,
    verbose: bool = True,
) -> gpd.GeoDataFrame:
    """Union of per-point buffers around every Indian positive, as GeoJSON."""
    boreholes = _read(
        "SELECT ST_Y(geom::geometry) AS lat, ST_X(geom::geometry) AS lon FROM boreholes"
    )
    left, bottom, right, top = SAUSAR_BBOX
    ngdr = _read(
        f"""
        SELECT ST_Y(geom::geometry) AS lat, ST_X(geom::geometry) AS lon
        FROM ngdr_national
        WHERE ST_X(geom::geometry) BETWEEN {left} AND {right}
          AND ST_Y(geom::geometry) BETWEEN {bottom} AND {top}
        """
    )
    xrf = _read(
        "SELECT ST_Y(geom::geometry) AS lat, ST_X(geom::geometry) AS lon FROM surface_samples"
    )

    all_points = pd.concat([boreholes, ngdr, xrf], ignore_index=True).dropna()
    if verbose:
        print(f"  boreholes        : {len(boreholes)}")
        print(f"  NGDR (in bbox)   : {len(ngdr)}")
        print(f"  surface samples  : {len(xrf)}")
        print(f"  total points     : {len(all_points)}")

    points = [Point(row.lon, row.lat) for row in all_points.itertuples()]

    # Latitude-corrected degree radius: a degree of longitude is only
    # cos(lat) x 111 km, so a flat /111 would under-buffer east-west.
    mean_lat = float(all_points.lat.mean())
    buffer_deg = buffer_km / (111.0 * math.cos(math.radians(mean_lat)))
    buffered = unary_union([p.buffer(buffer_deg) for p in points])

    gdf = gpd.GeoDataFrame(
        {
            "name": ["known_occurrence_buffer"],
            "buffer_km": [buffer_km],
            "n_points": [len(all_points)],
            "source": ["union_of_per_point_buffers_boreholes_xrf_ngdr"],
        },
        geometry=[buffered],
        crs="EPSG:4326",
    )

    path = Path(output_path) if output_path is not None else OUT_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    gdf.to_file(path, driver="GeoJSON")

    if verbose:
        area_km2 = float(gdf.to_crs("EPSG:6933").geometry.area.iloc[0] / 1e6)
        parts = getattr(buffered, "geoms", [buffered])
        print(f"  radius           : {buffer_km:.0f} km per point")
        print(f"  disjoint lobes   : {len(list(parts))}")
        print(f"  covered area     : {area_km2:,.0f} km2")
        print(f"  saved to         : {path}")

    return gdf


class OccurrenceBufferMask:
    """Point-in-buffer test with the same interface as GeologicalMask."""

    def __init__(
        self, mask_path: Path | str = OUT_PATH, mask_source: str = "occurrence_buffer_5km"
    ) -> None:
        self.mask_path = Path(mask_path)
        if not self.mask_path.exists():
            build_occurrence_buffer_mask(output_path=self.mask_path, verbose=False)
        self.gdf = gpd.read_file(self.mask_path)
        if self.gdf.crs is not None and self.gdf.crs.to_epsg() != 4326:
            self.gdf = self.gdf.to_crs("EPSG:4326")
        self.source = mask_source
        self.mask_geom = self.gdf.geometry.union_all()
        self._prepared = prep(self.mask_geom)

    def is_in_buffer(self, lat: float, lon: float) -> bool:
        return bool(self._prepared.contains(Point(lon, lat)))

    #: Alias so callers can treat both masks identically.
    def is_inside(self, lat: float, lon: float) -> bool:
        return self.is_in_buffer(lat, lon)

    def filter_score(self, lat: float, lon: float, score: float) -> tuple[float, str]:
        if self.is_in_buffer(lat, lon):
            return score, "kept_in_buffer"
        return 0.0, "masked_out_outside_buffer"


def main() -> None:
    print("=" * 60)
    print("KNOWN-OCCURRENCE BUFFER MASK")
    print("=" * 60)
    build_occurrence_buffer_mask()


if __name__ == "__main__":
    main()
