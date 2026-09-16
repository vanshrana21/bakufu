"""Pydantic response models for the Manganese Prospectivity API."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class BoreholeOut(BaseModel):
    """A single NGDR borehole collar."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    nuid: str
    borehole_no: str
    block_name: str
    district: str
    state: str
    lat: float
    lon: float
    length_m: float | None = None
    rl_collar_m: float | None = None
    rl_bottom_m: float | None = None
    borehole_type: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    commodity: str
    source: str


class BlockPriorOut(BaseModel):
    """Published or empirical grade envelope for a block."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    block_name: str
    district: str
    state: str
    mn_pct_min: float | None = None
    mn_pct_max: float | None = None
    mn_pct_typ: float | None = None
    fe_pct_min: float | None = None
    fe_pct_max: float | None = None
    sio2_pct_min: float | None = None
    sio2_pct_max: float | None = None
    al2o3_pct_min: float | None = None
    al2o3_pct_max: float | None = None
    p_pct_min: float | None = None
    p_pct_max: float | None = None
    ore_class: str | None = None
    host_formation: str | None = None
    source: str | None = None
    notes: str | None = None
    prior_type: str
    n_samples: int | None = None


class ForeignDepositOut(BaseModel):
    """A manganese deposit outside India."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    deposit_name: str
    country: str | None = None
    deposit_type: str
    host_rock: str | None = None
    age: str | None = None
    grade_pct: float | None = None
    tonnage: float | None = None
    lat: float
    lon: float
    source: str | None = None
    reference: str | None = None


class ForeignDepositPage(BaseModel):
    """One page of foreign deposits."""

    total: int
    page: int
    page_size: int
    items: list[ForeignDepositOut]


class PredictionOut(BaseModel):
    """A Phase 2 model output cell."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    geom_wkt: str
    prospectivity_score: float
    deposit_type: str
    uncertainty: float | None = None
    model_version: str
    created_at: datetime


class FeatureOut(BaseModel):
    """Raster-derived features sampled at a borehole collar."""

    borehole_id: int
    borehole_no: str
    lat: float
    lon: float
    features: dict[str, float | None]


class HealthOut(BaseModel):
    """Service liveness response.

    `status` is "degraded" when the model registry and the database disagree
    about what was published, or the active pointer cannot be followed: the API
    keeps serving the shipped model rather than going down, and says so here so
    a readiness check can catch it.
    """

    status: str
    version: str
    model_version: str
    model_source: str
    degraded: list[str] = []


# --- Phase 2: prospectivity predictions ---------------------------------


class PredictPointIn(BaseModel):
    """Request body for a single-point prediction."""

    lat: float = Field(..., ge=-90.0, le=90.0)
    lon: float = Field(..., ge=-180.0, le=180.0)


class ShapContribution(BaseModel):
    """One feature's contribution to a prediction, in log-odds space."""

    feature: str
    shap_value: float
    actual_value: float | None = None


class MaskInfoOut(BaseModel):
    """One available prediction mask."""

    id: str
    label: str
    source: str
    description: str
    production_source: str | None = None
    geojson_path: str | None = None


class PredictPointOut(BaseModel):
    """Scored location with its explanation."""

    prospectivity_score: float
    predicted_type: str
    uncertainty: float
    features_extracted: dict[str, float | None]
    shap_top5: list[ShapContribution]
    model_version: str
    lat: float
    lon: float
    prediction_id: int | None = None
    #: Masking is post-processing, so the pre-mask score stays visible.
    mask_applied: str = "none"
    mask_decision: str = "n/a"
    raw_score: float | None = None
    final_score: float | None = None


class PredictBboxIn(BaseModel):
    """Request body for a gridded bbox prediction."""

    min_lon: float = Field(..., ge=-180.0, le=180.0)
    min_lat: float = Field(..., ge=-90.0, le=90.0)
    max_lon: float = Field(..., ge=-180.0, le=180.0)
    max_lat: float = Field(..., ge=-90.0, le=90.0)
    grid_resolution_m: int = Field(100, gt=0, le=100_000)


class GridPrediction(BaseModel):
    """One scored grid cell."""

    lon: float
    lat: float
    score: float
    type: str
    raw_score: float | None = None
    mask_decision: str | None = None


class PredictBboxOut(BaseModel):
    """Scored grid over a bbox, highest score first."""

    predictions: list[GridPrediction]
    count: int
    bbox: list[float]
    grid_resolution_m: float
    cells_outside_raster: int
    model_version: str
    mask_applied: str = "none"
    cells_kept_by_mask: int | None = None


class PredictionRecordOut(BaseModel):
    """A stored prediction row."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    prospectivity_score: float
    deposit_type: str
    uncertainty: float | None = None
    model_version: str
    created_at: datetime


class TrainTaskOut(BaseModel):
    """Acknowledgement that background training has been queued."""

    task_id: str
    status: str
    detail: str | None = None


class TrainStatusOut(BaseModel):
    """Progress of a background training task."""

    task_id: str
    status: str
    started_at: datetime | None = None
    finished_at: datetime | None = None
    detail: str | None = None


# --- Phase 3: forecasting -------------------------------------------------


class ForecastOut(BaseModel):
    """One production forecast with its interval and component breakdown."""

    forecast_date: date
    target_period: date
    horizon_months: int
    predicted_tonnes: float
    predicted_lower_ci: float | None = None
    predicted_upper_ci: float | None = None
    model_version: str
    components: dict[str, float] = {}


class ShortfallRiskOut(BaseModel):
    """Shortfall risk for the most recent labelled month."""

    period_month: date
    risk_score: float
    risk_category: str
    contributing_factors: dict[str, float | None] = {}
    model_version: str
    decision_threshold: float | None = None


class AccuracyAtHorizon(BaseModel):
    """The shipped backtest row for one horizon."""

    mape: float
    naive_mape: float
    skill_vs_naive_pp: float
    ci80_coverage: float
    rmse: float
    n_origins: int


class ForecastModelMeta(BaseModel):
    """Which promoted Prophet bundle produced a forecast."""

    version: str
    variant: str
    regressors: list[str]
    trained_through: str
    changepoint_prior_scale: float
    mcmc_samples: int


class ForecastSeriesPoint(BaseModel):
    """One month of a multi-month forecast. p10/p90 bound the 80% interval."""

    month: str
    month_label: str
    p10: float
    p50: float
    p90: float


class ForecastResponse(BaseModel):
    """GET /forecast."""

    forecast_date: str
    target_period: str
    horizon_months: int
    predicted_tonnes: float
    predicted_lower_ci: float
    predicted_upper_ci: float
    ci_level: float
    components: dict[str, float]
    model: ForecastModelMeta
    accuracy_at_horizon: AccuracyAtHorizon | None
    series: list[ForecastSeriesPoint]


class ForecastHistoryHorizon(BaseModel):
    """Backtest metrics for one horizon."""

    horizon_months: int
    n_origins: int
    mape: float
    rmse: float
    naive_mape: float
    skill_vs_naive_pp: float
    ci80_coverage: float


class ForecastHistoryOrigin(BaseModel):
    """One rolling-origin backtest prediction."""

    horizon_months: int
    origin_month: str
    target_month: str
    actual_tonnes: float
    predicted_tonnes: float
    covered: bool


class ForecastHistoryBenchmark(BaseModel):
    name: str
    definition: str


class ForecastHistoryModel(BaseModel):
    version: str
    variant: str


class ForecastHistoryResponse(BaseModel):
    """GET /forecast/history."""

    horizons: list[ForecastHistoryHorizon]
    origins: list[ForecastHistoryOrigin]
    model: ForecastHistoryModel
    benchmark: ForecastHistoryBenchmark


class ProductionHistoryOut(BaseModel):
    """One month of MOIL production history."""

    period_month: date
    fiscal_year: str | None = None
    fiscal_quarter: int | None = None
    production_tonnes: float
    source_type: str
