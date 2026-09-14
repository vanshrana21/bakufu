"""
Geological formation mask for prospectivity predictions.

Currently uses Macrostrat's ~1:5M compilation (placeholder). Production
should replace with GSI Bhukosh 1:50K polygons - same interface, same
downstream logic, so only the file behind MASK_PATH changes.

Rationale: v6 has known false positives on tilled cropland outside
Precambrian metasedimentary basement. This mask filters predictions to
their geologically plausible context.

Scale caveat: at ~1:5M a single polygon spans tens of kilometres, so this
mask reliably separates basement from Deccan Trap basalt and alluvium but
cannot resolve a field boundary. Expect it to keep cropland that sits on
basement - see occurrence_buffer_mask for the tighter constraint.
"""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
from shapely.geometry import Point
from shapely.prepared import prep

from src.config.settings import settings

MASK_PATH: Path = (
    settings.DATA_RAW / "india" / "geology" / "sausar_precambrian_formations_macrostrat_proxy.geojson"
)


class GeologicalMask:
    """Point-in-basement test over a set of formation polygons."""

    def __init__(self, mask_path: Path | str = MASK_PATH, mask_source: str = "macrostrat_proxy") -> None:
        self.mask_path = Path(mask_path)
        self.gdf = gpd.read_file(self.mask_path)
        if self.gdf.crs is not None and self.gdf.crs.to_epsg() != 4326:
            self.gdf = self.gdf.to_crs("EPSG:4326")
        self.source = mask_source
        # union_all() replaces the deprecated unary_union in geopandas 1.x.
        self.mask_geom = self.gdf.geometry.union_all()
        # A prepared geometry makes repeated contains() cheap, which matters
        # for /predict/bbox scoring up to 1000 cells per call.
        self._prepared = prep(self.mask_geom)

    def is_in_basement(self, lat: float, lon: float) -> bool:
        """True if the point falls inside a Precambrian polygon."""
        return bool(self._prepared.contains(Point(lon, lat)))

    def filter_score(self, lat: float, lon: float, score: float) -> tuple[float, str]:
        """Apply mask to a prediction. Returns (filtered_score, decision)."""
        if self.is_in_basement(lat, lon):
            return score, "kept_in_basement"
        return 0.0, "masked_out_non_basement"

    def formations(self) -> list[str]:
        column = "formation_name" if "formation_name" in self.gdf.columns else self.gdf.columns[0]
        return sorted({str(v) for v in self.gdf[column].dropna()})

    def __len__(self) -> int:
        return len(self.gdf)
