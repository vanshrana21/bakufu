/** Raw backend response shapes, exactly as FastAPI sends them.
 *
 * Source of truth: backend `docs/phase_4/api_contracts.md` (v1.6/v1.7).
 * These are deliberately NOT the frontend contract types — the adapters in this
 * directory map between the two. Nothing outside lib/api/ should import from here.
 *
 * Fields marked `?` are ones the backend may or may not send depending on its
 * contract version. An adapter must handle both, never assume the newer shape.
 */

export interface WireProductionRow {
  report_month: string;              // "2026-05"
  mh_qty_tonnes: number;
  mp_qty_tonnes: number;
  mh_plus_mp_qty_tonnes: number;     // <- the series the chart plots
  all_india_qty_tonnes: number;
  extraction_method: "text" | "ocr" | string;
}
export interface WireProductionHistory {
  series: WireProductionRow[];
  coverage: {
    months_present: number;
    months_missing: number;
    date_range: { start: string; end: string };
    gaps: string[];
  };
  metadata: { source: string; proxy_note: string };
}

export interface WireForecastAccuracy {
  mape: number; naive_mape: number; skill_vs_naive_pp: number;
  ci80_coverage: number; rmse?: number; n_origins: number;
  /** Added in contract v1.8. `mape` describes the model that actually served
   * the horizon; this is Prophet's figure whichever model that was. */
  prophet_mape?: number;
}
/** NOTE: the `series[]` entries do NOT reuse the flat response's field names.
 * They are `month` / `p10` / `p50` / `p90`, whereas the top level uses
 * `target_period` / `predicted_lower_ci` / `predicted_tonnes` /
 * `predicted_upper_ci`. The last entry equals the top-level values. */
export interface WireForecastPoint {
  month: string;                     // "2026-06"
  month_label: string;               // "Jun 2026"
  p10: number;                       // lower bound of the 80% interval
  p50: number;                       // point estimate
  p90: number;                       // upper bound of the 80% interval
}
export interface WireForecast {
  forecast_date: string;             // "2026-09-09" — bare date, not ISO
  target_period: string;
  horizon_months: number;
  predicted_tonnes: number;
  predicted_lower_ci: number;
  predicted_upper_ci: number;
  ci_level: number;
  components: Record<string, number>;
  model: {
    version: string; variant: string; regressors: string[];
    trained_through: string;         // "2026-05"
    /** Null when seasonal-naive serves the horizon: both are Prophet settings. */
    changepoint_prior_scale: number | null; mcmc_samples: number | null;
    /** Added in contract v1.8: "mcmc_posterior" or
     * "empirical_backtest_ratio_quantiles". Says how the interval was built. */
    interval_method?: string;
  };
  /** Added in contract v1.8. The backend routes horizons 1-6 to seasonal-naive
   * and 12 to Prophet, on measured backtest MAPE, and names the choice here. */
  model_used?: "seasonal_naive" | "prophet" | string;
  reason?: string;
  accuracy_at_horizon: WireForecastAccuracy | null;
  /** Added in contract v1.9. Absent on older backends — see FORECAST_SERIES_REQUIRED. */
  series?: WireForecastPoint[];
}

export interface WireShapContribution {
  feature_name: string; human_label: string;
  value: number; display_value: string;
  shap_contribution: number;
  direction: "increases_risk" | "decreases_risk";
}
export interface WireShortfallRisk {
  as_of: string; forecast_month: string;
  shortfall_probability: number;
  risk_level: "low" | "medium" | "high";
  shortfall_definition: string;
  prophet_forecast_tonnes: number;
  shortfall_threshold_tonnes: number;
  feature_contributions: WireShapContribution[];
  shap_base_value: number;
  feature_provenance: { rainfall: string; prophet_forecast: string };
  model_metadata: {
    version: string; base_rate: number; roc_auc: number; pr_auc: number;
    trained_on_months: number; trained_on_positives: number; decision_threshold: number;
  };
}

export interface WireRecommendation {
  id: string;
  action_type: "schedule_adjustment" | "blasting_optimization" | "equipment_redeployment";
  title: string;
  rationale: string;
  equipment_referenced: string[];
  priority: "high" | "medium" | "low";
  driver: string;
  driver_label: string;
  triggered_by: Array<{ signal: string; value: number; display_value: string; shap_contribution: number }>;
  confidence: string;
}
export interface WireRecommendations {
  generated_at: string;
  context: {
    mine_name: string | null; mine_type: string | null;
    shortfall_probability: number; forecast_month: string;
    risk_level: string;
    drivers_ranked: Array<{ driver: string; label: string; positive_shap: number }>;
    footnotes: string[];
    message?: string;
    scenario_month?: string; is_historical_replay?: boolean; actual_shortfall?: boolean;
  };
  recommendations: WireRecommendation[];
  coverage_complete: boolean;
  action_types_included: string[];
  action_types_omitted: string[];
}

export interface WireDashboardSummary {
  generated_at: string;
  latest_actual: { month: string; mh_plus_mp_tonnes: number; all_india_tonnes: number } | null;
  next_forecast: { month: string; predicted_tonnes: number; lower_ci: number; upper_ci: number; ci_level: number } | null;
  shortfall: { month: string; probability: number; risk_level: string } | null;
  series_health: {
    months_present: number; months_missing: number;
    date_range: { start: string; end: string }; ocr_recovered_months: number;
  } | null;
  model_health: {
    forecast_version: string; shortfall_version: string;
    best_horizon: { horizon_months: number; mape: number; skill_vs_naive_pp: number } | null;
  };
  mines: { total: number; underground: number; opencast: number };
  degraded: string[];
  /** Added in contract v1.7 alongside the dev-artifact bundle. When
   * `synthetic` is true the served models are NOT the shipped trained ones. */
  data_provenance?: { origin: string; synthetic: boolean; note?: string };
}

export interface WireHeatmap {
  bbox: [number, number, number, number];
  grid: { n_cols: number; n_rows: number; cell_width_deg: number; cell_height_deg: number; origin: "top_left" };
  /** Row-major, n_rows arrays of n_cols. `null` = NO DATA, distinct from 0.0. */
  scores: Array<Array<number | null>>;
  cells: { cells_total: number; cells_outside_raster: number; cells_masked_out: number; cells_scored: number };
  score_range: { min: number; max: number; cap: number };
  mask_applied: string;
  model_version: string;
  generated_at: string;
  cached: boolean;
}

export interface WirePredictPoint {
  prospectivity_score: number;
  predicted_type: string;
  uncertainty: number;
  features_extracted: Record<string, number | null>;
  shap_top5: Array<{ feature: string; shap_value: number; actual_value: number }>;
  model_version: string;
  lat: number; lon: number;
  prediction_id: number | null;
  mask_applied: string;
  mask_decision: string;
  raw_score: number | null;
  final_score: number | null;
  /** Added in contract v1.10. The classifier's own probability and log-odds,
   * before the Elkan-Noto division and the 0.99 cap. Both of those compress
   * the top of the range, so every strong location reports 0.99 without
   * these. `model_margin` is what `shap_top5` explains. */
  raw_probability?: number | null;
  model_margin?: number | null;
}

export interface WireMaskInfo {
  id: string; label: string; source: string;
  description: string; production_source?: string; geojson_path?: string;
}

export interface WireMine {
  mine_name: string; state: string; district: string;
  mine_type: "underground" | "opencast" | "mixed";
  equipment: string[];
  capacity_target_tonnes: number | null;
  notes: string;
  sources: Array<{ tag: string; url: string }>;
  type_note: string | null;
  /** Added in contract v1.8 with the cited-coordinate pass. `source_url` is
   * null where the coordinate researcher supplied no full URL; the backend
   * stores null rather than guessing one. */
  lat: number; lon: number;
  confidence: "high" | "medium_high" | "low_medium" | "low" | "none";
  source: string;
  source_url: string | null;
  coordinate_precision: string | null;
  coordinate_note: string | null;
}
export interface WireMines {
  mines: WireMine[];
  counts: {
    total: number; underground: number; opencast: number; mixed: number;
    MH: number; MP: number;
    with_capacity_target: number; with_generic_fleet_only: number;
  };
}
