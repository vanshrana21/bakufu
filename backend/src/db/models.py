"""SQLAlchemy 2.0 ORM models for the manganese prospectivity database.

All geometries are stored in EPSG:4326 (WGS84 lon/lat) via PostGIS.
"""

from __future__ import annotations

from datetime import date, datetime

from geoalchemy2 import Geometry
from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

SRID: int = 4326


class Base(DeclarativeBase):
    """Declarative base for every table in this project."""


class Borehole(Base):
    """NGDR exploration borehole collar."""

    __tablename__ = "boreholes"
    __table_args__ = (UniqueConstraint("nuid", "borehole_no", name="uq_borehole_nuid_no"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nuid: Mapped[str] = mapped_column(String(64), index=True)
    borehole_no: Mapped[str] = mapped_column(String(64), index=True)
    block_name: Mapped[str] = mapped_column(String(128), index=True)
    district: Mapped[str] = mapped_column(String(128), index=True)
    state: Mapped[str] = mapped_column(String(128))
    geom: Mapped[str] = mapped_column(Geometry("POINT", srid=SRID))

    length_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    rl_collar_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    rl_bottom_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    borehole_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    start_date: Mapped[date | None] = mapped_column(nullable=True)
    end_date: Mapped[date | None] = mapped_column(nullable=True)

    commodity: Mapped[str] = mapped_column(String(64), default="Manganese")
    source: Mapped[str] = mapped_column(String(64), default="NGDR")


class BlockGradePrior(Base):
    """Published / empirical grade envelope for a named block."""

    __tablename__ = "block_grade_priors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    block_name: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    district: Mapped[str] = mapped_column(String(128))
    state: Mapped[str] = mapped_column(String(128))

    mn_pct_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    mn_pct_max: Mapped[float | None] = mapped_column(Float, nullable=True)
    mn_pct_typ: Mapped[float | None] = mapped_column(Float, nullable=True)
    fe_pct_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    fe_pct_max: Mapped[float | None] = mapped_column(Float, nullable=True)
    sio2_pct_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    sio2_pct_max: Mapped[float | None] = mapped_column(Float, nullable=True)
    al2o3_pct_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    al2o3_pct_max: Mapped[float | None] = mapped_column(Float, nullable=True)
    p_pct_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    p_pct_max: Mapped[float | None] = mapped_column(Float, nullable=True)

    ore_class: Mapped[str | None] = mapped_column(String(128), nullable=True)
    host_formation: Mapped[str | None] = mapped_column(String(256), nullable=True)
    source: Mapped[str | None] = mapped_column(String(512), nullable=True)
    notes: Mapped[str | None] = mapped_column(String, nullable=True)
    prior_type: Mapped[str] = mapped_column(String(32), default="PUBLISHED_REFERENCE")
    n_samples: Mapped[int | None] = mapped_column(Integer, nullable=True)


class SurfaceSample(Base):
    """Field surface sample with XRF geochemistry."""

    __tablename__ = "surface_samples"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sample_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    sample_type: Mapped[str] = mapped_column(String(64), default="surface_xrf")
    block_name: Mapped[str | None] = mapped_column(
        ForeignKey("block_grade_priors.block_name"), nullable=True, index=True
    )
    district: Mapped[str | None] = mapped_column(String(128), nullable=True)
    state: Mapped[str | None] = mapped_column(String(128), nullable=True)
    geom: Mapped[str] = mapped_column(Geometry("POINT", srid=SRID))

    mn_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    fe_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    si_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    sio2_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    al_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    al2o3_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    ca_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    p_pct: Mapped[float | None] = mapped_column(Float, nullable=True)

    notes: Mapped[str | None] = mapped_column(String, nullable=True)
    source: Mapped[str | None] = mapped_column(String(512), nullable=True)


class ForeignDeposit(Base):
    """Manganese deposit outside India (USGS / Geoscience Australia compilations)."""

    __tablename__ = "foreign_deposits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    deposit_name: Mapped[str] = mapped_column(String(256), index=True)
    country: Mapped[str | None] = mapped_column(String(128), index=True, nullable=True)
    deposit_type: Mapped[str] = mapped_column(String(32), default="UNKNOWN", index=True)
    host_rock: Mapped[str | None] = mapped_column(String(512), nullable=True)
    age: Mapped[str | None] = mapped_column(String(128), nullable=True)
    grade_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    tonnage: Mapped[float | None] = mapped_column(Float, nullable=True)
    geom: Mapped[str] = mapped_column(Geometry("POINT", srid=SRID))
    source: Mapped[str | None] = mapped_column(String(256), nullable=True)
    reference: Mapped[str | None] = mapped_column(String, nullable=True)


class NgdrNational(Base):
    """Point features from the NGDR national manganese bundle, layer-tagged."""

    __tablename__ = "ngdr_national"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_layer: Mapped[str] = mapped_column(String(64), index=True)
    geom: Mapped[str] = mapped_column(Geometry("POINT", srid=SRID))
    commodity: Mapped[str] = mapped_column(String(64), default="Manganese")
    primary_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    host_rock: Mapped[str | None] = mapped_column(String(512), nullable=True)
    state: Mapped[str | None] = mapped_column(String(128), index=True, nullable=True)
    raw_props: Mapped[dict] = mapped_column(JSON, default=dict)
    #: 'point' for natively-point layers, 'polygon_centroid' where the loader
    #: reduced a polygon footprint to an interior representative point.
    #: Phase 2 weights labels by this. Set by scripts/migrations/add_ngdr_geom_type.py.
    source_geometry_type: Mapped[str | None] = mapped_column(String(20), nullable=True)


class Prediction(Base):
    """Model output cell. Populated in Phase 2; empty for now."""

    __tablename__ = "predictions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    geom: Mapped[str] = mapped_column(Geometry("POLYGON", srid=SRID))
    prospectivity_score: Mapped[float] = mapped_column(Float)
    deposit_type: Mapped[str] = mapped_column(String(32), default="UNKNOWN")
    uncertainty: Mapped[float | None] = mapped_column(Float, nullable=True)
    model_version: Mapped[str] = mapped_column(String(64))
    #: Post-processing mask that produced final_score. prospectivity_score
    #: mirrors final_score; raw_score keeps the pre-mask value so a masked-out
    #: cell can still be inspected.
    mask_applied: Mapped[str | None] = mapped_column(String(50), nullable=True)
    raw_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    final_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )



class MoilMonthlyProduction(Base):
    """MOIL company-wide monthly production, from BSE filings / reports."""

    __tablename__ = "moil_monthly_production"
    __table_args__ = (
        UniqueConstraint("period_month", "source_type", name="uq_moil_period_source"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    filing_date: Mapped[date | None] = mapped_column(nullable=True)
    period_month: Mapped[date] = mapped_column(index=True)
    fiscal_year: Mapped[str | None] = mapped_column(String(16), index=True, nullable=True)
    fiscal_quarter: Mapped[int | None] = mapped_column(Integer, nullable=True)
    production_tonnes: Mapped[float] = mapped_column(Float)
    source_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    source_type: Mapped[str] = mapped_column(String(32), default="BSE_filing")
    notes: Mapped[str | None] = mapped_column(String, nullable=True)


class ImdRainfallDaily(Base):
    """Daily rainfall for the MOIL mining districts."""

    __tablename__ = "imd_rainfall_daily"
    __table_args__ = (UniqueConstraint("date", "district", name="uq_rainfall_date_district"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    date: Mapped[date] = mapped_column(index=True)
    district: Mapped[str] = mapped_column(String(64), index=True)
    state: Mapped[str | None] = mapped_column(String(64), nullable=True)
    rainfall_mm: Mapped[float] = mapped_column(Float)
    normal_rainfall_mm: Mapped[float | None] = mapped_column(Float, nullable=True)
    departure_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    source: Mapped[str] = mapped_column(String(64), default="open_meteo_archive")


class ProductionForecast(Base):
    """One forecast row: made on `forecast_date`, about `target_period`."""

    __tablename__ = "production_forecasts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    forecast_date: Mapped[date] = mapped_column(index=True)
    target_period: Mapped[date] = mapped_column(index=True)
    predicted_tonnes: Mapped[float] = mapped_column(Float)
    predicted_lower_ci: Mapped[float | None] = mapped_column(Float, nullable=True)
    predicted_upper_ci: Mapped[float | None] = mapped_column(Float, nullable=True)
    model_version: Mapped[str] = mapped_column(String(32), default="prophet_v1")
    horizon_months: Mapped[int] = mapped_column(Integer, default=1)


class ShortfallRisk(Base):
    """Shortfall risk score for one month, with its contributing factors."""

    __tablename__ = "shortfall_risks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    period_month: Mapped[date] = mapped_column(index=True)
    risk_score: Mapped[float] = mapped_column(Float)
    risk_category: Mapped[str] = mapped_column(String(16), default="LOW")
    contributing_factors: Mapped[dict] = mapped_column(JSON, default=dict)
    model_version: Mapped[str] = mapped_column(String(32), default="shortfall_v1")


#: Creation order respected by init_db (FKs first).
ALL_TABLES: list[type[Base]] = [
    Borehole,
    BlockGradePrior,
    SurfaceSample,
    ForeignDeposit,
    NgdrNational,
    Prediction,
    MoilMonthlyProduction,
    ImdRainfallDaily,
    ProductionForecast,
    ShortfallRisk,
]
