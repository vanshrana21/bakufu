"""Application settings, project paths and domain constants for the Sausar belt."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Repository root: src/config/settings.py -> src/config -> src -> <root>
PROJECT_ROOT: Path = Path(__file__).resolve().parents[2]

DATA_RAW: Path = PROJECT_ROOT / "data" / "raw"
DATA_PROCESSED: Path = PROJECT_ROOT / "data" / "processed"
MODELS_DIR: Path = PROJECT_ROOT / "models"

# Smoke-test rasters used as the Phase 1 feature source.
S2_SMOKE_TEST: Path = DATA_RAW / "satellite" / "s2_nagpur_smoke_test.tif"
DEM_SMOKE_TEST: Path = DATA_RAW / "dem" / "dem_nagpur_smoke_test.tif"

#: Heatmap viewports pre-computed at API startup so demo-day first requests
#: are already warm. Chosen for raster coverage: all three sit fully inside
#: the usable S2-and-DEM footprint (lat 21.3-22.1), so none contain null
#: cells. A Nagpur viewport was considered and rejected - the DEM stops at
#: 21.3 and three Nagpur mines lie south of it. See docs/known_issues.md #5.
HEATMAP_WARM_VIEWPORTS: list[dict[str, object]] = [
    {"name": "full_bbox", "bbox": [79.0, 21.3, 80.6, 22.1], "grid_size": 32},
    {"name": "balaghat_bhandara", "bbox": [79.53, 21.32, 80.57, 22.05], "grid_size": 32},
    {"name": "balaghat_ukwa", "bbox": [80.05, 21.70, 80.60, 22.05], "grid_size": 32},
]

#: Historical months the recommendations demo can replay. Each is a real
#: shortfall the shipped classifier flags at p >= 0.60, chosen for a rich
#: spread of positive SHAP across drivers so the cards differ:
#:   2021-04  rainfall-led   (rain 1.567 > history 1.441)
#:   2024-02  forecast-led   (level 2.247 > history 1.601 > rain 0.740)
#: Swap these freely - nothing else depends on the values. Months before
#: 2021-04 are unavailable: the label-contamination cut starts there.
SCENARIO_MONTHS: list[str] = ["2021-04", "2024-02"]

# Sausar belt area of interest: [min_lon, min_lat, max_lon, max_lat] in EPSG:4326.
BBOX: list[float] = [79.0, 21.3, 80.6, 22.1]

# Sentinel-2 band order as stacked in the smoke-test GeoTIFF.
S2_BANDS: list[str] = ["B02", "B03", "B04", "B08", "B11", "B12"]

# MOIL manganese mines: {name: (lat, lon, block_name)}
MOIL_MINES: dict[str, tuple[float, float, str]] = {
    "Balaghat": (21.8167, 80.1833, "Balaghat"),
    "Ukwa": (21.9500, 80.4667, "Ukwa"),
    "Dongri Buzurg": (21.4667, 79.6333, "Dongri Buzurg"),
    "Chikla": (21.4167, 79.7500, "Chikla"),
    "Tirodi": (21.6667, 79.7167, "Tirodi"),
    "Gumgaon": (21.2333, 78.9333, "Gumgaon"),
    "Kandri": (21.2667, 79.0000, "Kandri"),
    "Munsar": (21.3167, 79.1667, "Munsar"),
    "Beldongri": (21.2833, 79.0500, "Beldongri"),
    # Corrected 2026-09-09: was (21.3333, 79.2000), which falls in Maharashtra
    # near the Nagpur cluster. Sitapatore is in Balaghat district, Madhya
    # Pradesh - confirmed against the International Manganese Institute, MOIL's
    # About page, the IBM 2022 yearbook and a MOIL CMD interview, and
    # consistent with docs/moil_reference/equipment_deployment.md listing it
    # under Madhya Pradesh. Coordinate is approximate to district level.
    "Sitapatore": (21.8500, 80.2000, "Sitapatore"),
}


class Settings(BaseSettings):
    """Environment-backed settings, loaded from the project-root .env."""

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    DATABASE_URL: str = ""
    SUPABASE_URL: str = ""
    SUPABASE_KEY: str = ""
    #: When set, every route except the health check requires this value in the
    #: X-API-Key header (src/api/security.py). Blank keeps the API open.
    API_KEY: str = ""

    # Re-exported so callers only need to import Settings.
    PROJECT_ROOT: Path = PROJECT_ROOT
    DATA_RAW: Path = DATA_RAW
    DATA_PROCESSED: Path = DATA_PROCESSED
    MODELS_DIR: Path = MODELS_DIR

    BBOX: list[float] = BBOX
    S2_BANDS: list[str] = S2_BANDS
    MOIL_MINES: dict[str, tuple[float, float, str]] = MOIL_MINES
    HEATMAP_WARM_VIEWPORTS: list[dict[str, object]] = HEATMAP_WARM_VIEWPORTS
    SCENARIO_MONTHS: list[str] = SCENARIO_MONTHS

    @property
    def s2_smoke_test(self) -> Path:
        return self.DATA_RAW / "satellite" / "s2_nagpur_smoke_test.tif"

    @property
    def dem_smoke_test(self) -> Path:
        return self.DATA_RAW / "dem" / "dem_nagpur_smoke_test.tif"

    def require_database_url(self) -> str:
        """Return DATABASE_URL or raise a clear error if it is not configured."""
        if not self.DATABASE_URL:
            raise RuntimeError(
                "DATABASE_URL is not set. Add it to .env at the project root:\n"
                "  DATABASE_URL=postgresql+psycopg://postgres:PASSWORD@HOST:5432/postgres"
            )
        return self.DATABASE_URL


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton."""
    return Settings()


settings: Settings = get_settings()
