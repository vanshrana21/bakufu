"""Application settings, project paths and domain constants for the Sausar belt."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Repository root: src/config/settings.py -> src/config -> src -> <root>
PROJECT_ROOT: Path = Path(__file__).resolve().parents[2]

DATA_RAW: Path = PROJECT_ROOT / "data" / "raw"
DATA_PROCESSED: Path = PROJECT_ROOT / "data" / "processed"
MODELS_DIR: Path = PROJECT_ROOT / "models"

# Smoke-test rasters used as the Phase 1 feature source.
S2_SMOKE_TEST: Path = DATA_RAW / "satellite" / "s2_nagpur_smoke_test.tif"
DEM_SMOKE_TEST: Path = DATA_RAW / "dem" / "dem_nagpur_smoke_test.tif"

#: The mosaic prospectivity v6 was trained on. Read-only: never overwritten.
S2_TRAINING_PATH: Path = DATA_RAW / "satellite" / "s2_sausar_v2.tif"

#: What the prospectivity API scores from. The training mosaic byte-for-byte
#: plus a western strip that brings Gumgaon inside the footprint, built by
#: src/data/ingest/fetch_gumgaon_strip.py. The smoke-test rasters above stay
#: the Phase 1 feature source for /boreholes and the feature tests.
S2_SERVING_PATH: Path = DATA_RAW / "satellite" / "s2_moil_operational_v1.tif"
DEM_SERVING_PATH: Path = DATA_RAW / "dem" / "dem_moil_operational.tif"

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

# MOIL operating mines with coordinate provenance, reconciled 2026-09-13 from
# docs/moil_coordinate_sources.md. Equipment, capacity and fleet notes stay in
# src/reference/moil_mines.py; tests/test_mine_coordinates.py fails if the two
# disagree on state, district or type.
#
# `source_url` is None where the submitted link was truncated: the source is
# named, but no full URL has been provided, and a guessed address would be an
# invented citation.
#
# Tirodi and Dongri Buzurg keep type "opencast" from the reference module. The
# coordinate submission listed both as underground, but on Wikipedia settlement
# proxies only, which is not a primary source for a mine's type.
MOIL_MINES: dict[str, dict[str, Any]] = {
    "Balaghat": {
        "lat": 21.8333, "lon": 80.2333,
        "state": "Madhya Pradesh", "district": "Balaghat",
        "type": "underground",
        "confidence": "high",
        "source": "MoEFCC PFR boundary centroid + subsidence report (forestsclearance.nic.in)",
        "source_url": None,
        "coordinate_precision": None,
        "note": None,
    },
    "Ukwa": {
        "lat": 21.9667, "lon": 80.4667,
        "state": "Madhya Pradesh", "district": "Balaghat",
        "type": "underground",
        "confidence": "high",
        "source": "MoEFCC subsidence report + Wikipedia agree",
        "source_url": "https://en.wikipedia.org/wiki/Ukwa",
        "coordinate_precision": None,
        "note": None,
    },
    "Dongri Buzurg": {
        "lat": 21.5500, "lon": 79.6941,
        "state": "Maharashtra", "district": "Bhandara",
        "type": "opencast",
        "confidence": "low_medium",
        "source": "Wikipedia railway station proxy (no EC/PFR found)",
        "source_url": "https://en.wikipedia.org/wiki/Dongri_Buzurg_railway_station",
        "coordinate_precision": "approximate — 1-2 km from actual mine boundary",
        "note": None,
    },
    "Chikla": {
        "lat": 21.5443, "lon": 79.7614,
        "state": "Maharashtra", "district": "Bhandara",
        "type": "underground",
        "confidence": "high",
        "source": "MPCB EC Executive Summary boundary centroid (mpcb.gov.in)",
        "source_url": None,
        "coordinate_precision": None,
        "note": None,
    },
    "Tirodi": {
        "lat": 21.6830, "lon": 79.7310,
        "state": "Madhya Pradesh", "district": "Balaghat",
        "type": "opencast",
        "confidence": "low_medium",
        "source": "Wikipedia Tirodi town proxy (no mine-specific EC found)",
        "source_url": "https://en.wikipedia.org/wiki/Tirodi",
        "coordinate_precision": "approximate — town centroid, mine may be 1-3 km offset",
        "note": None,
    },
    "Gumgaon": {
        "lat": 21.400, "lon": 78.980,
        "state": "Maharashtra", "district": "Nagpur",
        "type": "underground",
        "confidence": "high",
        "source": "MoEFCC PFR 95-pillar boundary centroid (environmentclearance.nic.in)",
        "source_url": None,
        "coordinate_precision": None,
        "note": None,
    },
    "Kandri": {
        "lat": 21.4125, "lon": 79.2667,
        "state": "Maharashtra", "district": "Nagpur",
        "type": "underground",
        "confidence": "high",
        "source": "MPCB EC Executive Summary (overrides Wikipedia — different village)",
        "source_url": None,
        "coordinate_precision": None,
        "note": "Wikipedia's Kandri entry refers to a different village at 19.98N 80.43E",
    },
    "Munsar": {
        "lat": 21.3958, "lon": 79.2792,
        "state": "Maharashtra", "district": "Nagpur",
        "type": "underground",
        "confidence": "medium_high",
        "source": "MoEFCC PFR stated center of two lease blocks (environmentclearance.nic.in)",
        "source_url": None,
        "coordinate_precision": None,
        "note": None,
    },
    "Beldongri": {
        "lat": 21.3495, "lon": 79.3003,
        "state": "Maharashtra", "district": "Nagpur",
        "type": "underground",
        "confidence": "low",
        "source": "USGS MRDS via TheDiggings.com (no MoEFCC/AR/Wikipedia coord)",
        "source_url": None,
        "coordinate_precision": "approximate — USGS third-party database",
        "note": None,
    },
    "Sitapatore": {
        "lat": 21.7000, "lon": 79.6667,
        "state": "Madhya Pradesh", "district": "Balaghat",
        "type": "opencast",
        "confidence": "high",
        "source": "MOIL Mining Plan (forestsclearance.nic.in) + cross-referenced with MOIL AR 2025-26",
        "source_url": "https://forestsclearance.nic.in/DownloadPdfFile.aspx?FileName=611712291216JLTFUMiningplan.pdf",
        "coordinate_precision": None,
        "note": (
            "Village Sitapatore, PO Sukli, Tirodi tehsil. Located ~12 km from the "
            "larger Tirodi Manganese Mine. Regional deposit area extends slightly "
            "south (21.6667N 79.6667E per Mindat)."
        ),
    },
}


def get_verified_mines() -> dict[str, dict[str, Any]]:
    """Returns only mines with confidence != 'none'."""
    return {name: mine for name, mine in MOIL_MINES.items() if mine["confidence"] != "none"}


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
    #: Shared key every API request must carry in the X-API-Key header
    #: (src/api/security.py). Optional here so scripts and the Celery worker can
    #: load settings without it; the API server loads ServerSettings, which
    #: refuses to start when it is missing.
    API_KEY: SecretStr | None = None

    #: Extra browser origins allowed to call the API directly, comma separated.
    #: The local dev servers are always allowed; a deployed frontend origin has
    #: to be named here, or its browser calls are refused by CORS - which is
    #: why a production deployment behaves differently from a local one.
    CORS_EXTRA_ORIGINS: str = ""

    #: Broker for the Celery worker that runs POST /train (src/worker).
    CELERY_BROKER_URL: str = "redis://127.0.0.1:6379/0"
    #: A training worker renews its job's lease this often...
    TRAINING_HEARTBEAT_SECONDS: int = 30
    #: ...and a running job whose lease is older than this has lost its worker.
    TRAINING_LEASE_SECONDS: int = 150
    #: A queued job that no worker has claimed within this long is failed.
    TRAINING_QUEUE_TIMEOUT_SECONDS: int = 30 * 60
    #: Whether a finished training job may point serving at its own artifact.
    #: On, but never unconditionally: the candidate has to take the same
    #: features as the model it would replace, beat chance and the base rate,
    #: and not fall materially below what is serving (src/models/registry.py
    #: acceptance_report). A candidate that fails is still published, and the
    #: job says why it was not activated. Turn this off to require
    #: `python -m scripts.promote_model` for every promotion.
    TRAINING_ACTIVATE_ON_SUCCESS: bool = True
    #: Celery time limits for one training run: the soft limit raises inside the
    #: task so the failure is recorded, the hard limit kills the process.
    TRAINING_SOFT_TIME_LIMIT_SECONDS: int = 2 * 3600
    TRAINING_TIME_LIMIT_SECONDS: int = 2 * 3600 + 300

    # Re-exported so callers only need to import Settings.
    PROJECT_ROOT: Path = PROJECT_ROOT
    DATA_RAW: Path = DATA_RAW
    DATA_PROCESSED: Path = DATA_PROCESSED
    MODELS_DIR: Path = MODELS_DIR
    S2_TRAINING_PATH: Path = S2_TRAINING_PATH
    S2_SERVING_PATH: Path = S2_SERVING_PATH
    DEM_SERVING_PATH: Path = DEM_SERVING_PATH

    BBOX: list[float] = BBOX
    S2_BANDS: list[str] = S2_BANDS
    MOIL_MINES: dict[str, dict[str, Any]] = MOIL_MINES
    HEATMAP_WARM_VIEWPORTS: list[dict[str, object]] = HEATMAP_WARM_VIEWPORTS
    SCENARIO_MONTHS: list[str] = SCENARIO_MONTHS

    @property
    def s2_smoke_test(self) -> Path:
        return self.DATA_RAW / "satellite" / "s2_nagpur_smoke_test.tif"

    @property
    def dem_smoke_test(self) -> Path:
        return self.DATA_RAW / "dem" / "dem_nagpur_smoke_test.tif"

    @model_validator(mode="after")
    def _training_timings_are_consistent(self) -> Settings:
        if self.TRAINING_HEARTBEAT_SECONDS <= 0:
            raise ValueError("TRAINING_HEARTBEAT_SECONDS must be positive")
        # Three missed heartbeats before a lease lapses, so one slow database
        # round trip never hands a live job to a second worker.
        if self.TRAINING_LEASE_SECONDS < 3 * self.TRAINING_HEARTBEAT_SECONDS:
            raise ValueError("TRAINING_LEASE_SECONDS must be at least 3x TRAINING_HEARTBEAT_SECONDS")
        if not 0 < self.TRAINING_SOFT_TIME_LIMIT_SECONDS < self.TRAINING_TIME_LIMIT_SECONDS:
            raise ValueError(
                "TRAINING_SOFT_TIME_LIMIT_SECONDS must be positive and below TRAINING_TIME_LIMIT_SECONDS"
            )
        return self

    def require_database_url(self) -> str:
        """Return DATABASE_URL or raise a clear error if it is not configured."""
        if not self.DATABASE_URL:
            raise RuntimeError(
                "DATABASE_URL is not set. Add it to .env at the project root:\n"
                "  DATABASE_URL=postgresql+psycopg://postgres:PASSWORD@HOST:5432/postgres"
            )
        return self.DATABASE_URL


class ServerSettings(Settings):
    """Settings the API server boots with. Fails closed without an API key."""

    @field_validator("API_KEY", mode="after")
    @classmethod
    def _api_key_is_required(cls, value: SecretStr | None) -> SecretStr:
        if value is None or not value.get_secret_value().strip():
            raise ValueError(
                "API_KEY is missing or empty, and the API refuses to start without it. "
                "Set API_KEY in backend/.env - generate one with "
                "python -c \"import secrets; print(secrets.token_urlsafe(32))\" - "
                "and put the same value in frontend/.env.local as BAKUFU_API_KEY."
            )
        return value


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton."""
    return Settings()


@lru_cache
def get_server_settings() -> ServerSettings:
    """Validated settings for the API process.

    Raises pydantic's ValidationError, a ValueError, when API_KEY is missing or
    empty. src/api/main.py calls this before it creates the app.
    """
    return ServerSettings()


settings: Settings = get_settings()
