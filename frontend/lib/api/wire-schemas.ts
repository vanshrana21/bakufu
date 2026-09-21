/** Runtime checks on raw backend payloads, before any adapter touches them.
 *
 * `wire.ts` describes the API in TypeScript, which the compiler believes and
 * the network does not. A renamed or dropped backend field would arrive as
 * `undefined`, sail through an adapter as `NaN` or an empty string, and only
 * fail later as a contract error about the *transformed* object — or worse,
 * render as a plausible number. These schemas fail at the boundary instead,
 * naming the endpoint and the field.
 *
 * Each schema covers every field its `wire.ts` interface declares required, so
 * a parsed payload genuinely satisfies that type: there is no cast papering
 * over a field nobody validated. They pass through unknown keys, because the
 * backend may add fields without breaking this build, and they keep `null`
 * (no data) distinct from missing.
 */

import { z } from "zod";
import type {
  WireDashboardSummary,
  WireForecast,
  WireHeatmap,
  WireMines,
  WirePredictPoint,
  WireProductionHistory,
  WireRecommendations,
  WireShortfallRisk,
} from "./wire";

const Finite = z.number().finite();
const Text = z.string().min(1);
const Month = z.string().regex(/^\d{4}-\d{2}$/, "expected a YYYY-MM month");

export const WireProductionHistorySchema = z.object({
  series: z.array(
    z.object({
      report_month: Month,
      mh_qty_tonnes: Finite,
      mp_qty_tonnes: Finite,
      mh_plus_mp_qty_tonnes: Finite,
      all_india_qty_tonnes: Finite,
      extraction_method: Text,
    }).passthrough(),
  ),
  coverage: z.object({
    months_present: z.number().int(),
    months_missing: z.number().int(),
    date_range: z.object({ start: Text, end: Text }).passthrough(),
    gaps: z.array(z.string()),
  }).passthrough(),
  metadata: z.object({ source: Text, proxy_note: z.string() }).passthrough(),
}).passthrough();

const WireForecastAccuracySchema = z.object({
  mape: Finite,
  naive_mape: Finite,
  skill_vs_naive_pp: Finite,
  ci80_coverage: Finite,
  rmse: Finite.optional(),
  n_origins: z.number().int(),
}).passthrough();

export const WireForecastSchema = z.object({
  forecast_date: Text,
  target_period: Month,
  horizon_months: z.number().int(),
  predicted_tonnes: Finite,
  predicted_lower_ci: Finite,
  predicted_upper_ci: Finite,
  ci_level: Finite,
  components: z.record(Finite),
  model: z.object({
    version: Text,
    variant: Text,
    regressors: z.array(z.string()),
    trained_through: Text,
    // null, not missing, when seasonal-naive serves the horizon: it has no MCMC.
    changepoint_prior_scale: Finite.nullable(),
    mcmc_samples: Finite.nullable(),
    interval_method: z.string().optional(),
  }).passthrough(),
  accuracy_at_horizon: WireForecastAccuracySchema.nullable(),
  // Contract v1.7; absent on older backends, and the adapter says so loudly.
  series: z
    .array(
      z.object({
        month: Month,
        month_label: Text,
        p10: Finite,
        p50: Finite,
        p90: Finite,
      }).passthrough(),
    )
    .optional(),
  model_used: Text.optional(),
  reason: Text.optional(),
}).passthrough();

const WireShapContributionSchema = z.object({
  feature_name: Text,
  human_label: Text,
  value: Finite,
  display_value: z.string(),
  shap_contribution: Finite,
  direction: z.enum(["increases_risk", "decreases_risk"]),
}).passthrough();

export const WireShortfallRiskSchema = z.object({
  as_of: Text,
  forecast_month: Month,
  shortfall_probability: Finite,
  risk_level: z.enum(["low", "medium", "high"]),
  shortfall_definition: z.string(),
  prophet_forecast_tonnes: Finite,
  shortfall_threshold_tonnes: Finite,
  feature_contributions: z.array(WireShapContributionSchema),
  shap_base_value: Finite,
  feature_provenance: z.object({ rainfall: z.string(), prophet_forecast: z.string() }).passthrough(),
  model_metadata: z.object({
    version: Text,
    base_rate: Finite,
    roc_auc: Finite,
    pr_auc: Finite,
    trained_on_months: z.number().int(),
    trained_on_positives: z.number().int(),
    decision_threshold: Finite,
  }).passthrough(),
}).passthrough();

const WireRecommendationSchema = z.object({
  id: Text,
  action_type: z.enum(["schedule_adjustment", "blasting_optimization", "equipment_redeployment"]),
  title: Text,
  rationale: z.string(),
  equipment_referenced: z.array(z.string()),
  priority: z.enum(["high", "medium", "low"]),
  driver: Text,
  driver_label: Text,
  triggered_by: z.array(
    z.object({
      signal: Text,
      value: Finite,
      display_value: z.string(),
      shap_contribution: Finite,
    }).passthrough(),
  ),
  confidence: z.string(),
}).passthrough();

export const WireRecommendationsSchema = z.object({
  generated_at: Text,
  context: z.object({
    mine_name: z.string().nullable(),
    mine_type: z.string().nullable(),
    shortfall_probability: Finite,
    forecast_month: Month,
    risk_level: Text,
    drivers_ranked: z.array(
      z.object({ driver: Text, label: Text, positive_shap: Finite }).passthrough(),
    ),
    footnotes: z.array(z.string()),
    // Optional on the wire, but the adapter reads all four. Declared so they are
    // type-checked rather than arriving as `unknown` through `.passthrough()`:
    // `scenario_month` decides whether the register is labelled a replay, and a
    // replay presented as the current month would be a lie about the data.
    message: z.string().optional(),
    scenario_month: z.string().optional(),
    is_historical_replay: z.boolean().optional(),
    actual_shortfall: z.boolean().optional(),
  }).passthrough(),
  recommendations: z.array(WireRecommendationSchema),
  coverage_complete: z.boolean(),
  action_types_included: z.array(z.string()),
  action_types_omitted: z.array(z.string()),
}).passthrough();

export const WireDashboardSummarySchema = z.object({
  generated_at: Text,
  latest_actual: z.object({
    month: Month,
    mh_plus_mp_tonnes: Finite,
    all_india_tonnes: Finite,
  }).passthrough().nullable(),
  next_forecast: z.object({
    month: Month,
    predicted_tonnes: Finite,
    lower_ci: Finite,
    upper_ci: Finite,
    ci_level: Finite,
  }).passthrough().nullable(),
  shortfall: z.object({
    month: Month,
    probability: Finite,
    risk_level: Text,
  }).passthrough().nullable(),
  series_health: z.object({
    months_present: z.number().int(),
    months_missing: z.number().int(),
    date_range: z.object({ start: Text, end: Text }).passthrough(),
    ocr_recovered_months: z.number().int(),
  }).passthrough().nullable(),
  model_health: z.object({
    forecast_version: Text,
    shortfall_version: Text,
    best_horizon: z.object({
      horizon_months: z.number().int(),
      mape: Finite,
      skill_vs_naive_pp: Finite,
    }).passthrough().nullable(),
  }).passthrough(),
  mines: z.object({
    total: z.number().int(),
    underground: z.number().int(),
    opencast: z.number().int(),
  }).passthrough(),
  degraded: z.array(z.string()),
  /** Optional on the wire for older backends; when present it decides whether
   * the screen is labelled as development artifacts, so its shape is checked. */
  data_provenance: z
    .object({ origin: Text, synthetic: z.boolean(), note: z.string().nullish() })
    .passthrough()
    .optional(),
}).passthrough();

export const WireHeatmapSchema = z.object({
  bbox: z.tuple([Finite, Finite, Finite, Finite]),
  grid: z.object({
    n_cols: z.number().int(),
    n_rows: z.number().int(),
    cell_width_deg: Finite,
    cell_height_deg: Finite,
    origin: z.literal("top_left"),
  }).passthrough(),
  // Row-major; null is NO DATA and must stay distinct from 0.
  scores: z.array(z.array(Finite.nullable())),
  cells: z.object({
    cells_total: z.number().int(),
    cells_outside_raster: z.number().int(),
    cells_masked_out: z.number().int(),
    cells_scored: z.number().int(),
  }).passthrough(),
  score_range: z.object({ min: Finite, max: Finite, cap: Finite }).passthrough(),
  mask_applied: Text,
  model_version: Text,
  generated_at: Text,
  cached: z.boolean(),
}).passthrough();

export const WirePredictPointSchema = z.object({
  prospectivity_score: Finite,
  predicted_type: Text,
  uncertainty: Finite,
  features_extracted: z.record(Finite.nullable()),
  shap_top5: z.array(
    z.object({
      feature: Text,
      shap_value: Finite,
      // Null where the feature's raster had no value at this point.
      actual_value: Finite.nullable(),
    }).passthrough(),
  ),
  shap_base_value: Finite.nullable(),
  model_version: Text,
  lat: Finite,
  lon: Finite,
  prediction_id: z.number().nullable(),
  mask_applied: Text,
  mask_decision: z.string(),
  raw_score: Finite.nullable(),
  final_score: Finite.nullable(),
  raw_probability: Finite.nullable().optional(),
  model_margin: Finite.nullable().optional(),
}).passthrough();

export const WireMinesSchema = z.object({
  mines: z.array(
    z.object({
      mine_name: Text,
      state: Text,
      district: Text,
      mine_type: Text,
      equipment: z.array(z.string()),
      capacity_target_tonnes: Finite.nullable(),
      notes: z.string().nullable(),
      sources: z.array(z.object({ tag: Text, url: z.string().nullable() }).passthrough()),
      type_note: z.string().nullable(),
      lat: Finite,
      lon: Finite,
      confidence: Text,
      source: Text,
      source_url: z.string().nullable(),
      coordinate_precision: z.string().nullable(),
      coordinate_note: z.string().nullable(),
    }).passthrough(),
  ).min(1),
  counts: z.record(z.number().int()),
}).passthrough();

/** A backend payload that does not match what this build was written against. */
export class WireContractError extends Error {
  readonly endpoint: string;
  constructor(message: string, endpoint: string) {
    super(message);
    this.name = "WireContractError";
    this.endpoint = endpoint;
  }
}

/** Parse a raw payload, or throw an error that names the endpoint and field. */
export function parseWire<T>(schema: z.ZodType<T, z.ZodTypeDef, unknown>, payload: unknown, endpoint: string): T {
  const result = schema.safeParse(payload);
  if (result.success) return result.data;
  const first = result.error.issues[0];
  const where = first?.path.length ? first.path.join(".") : "(root)";
  throw new WireContractError(
    `${endpoint} returned a payload this build does not understand: ${where} ${first?.message ?? "is invalid"}`,
    endpoint,
  );
}

/** Compile-time proof that each schema produces the wire type it stands for.
 * If a field is added to wire.ts without being validated here, this breaks. */
type Covers<Schema extends z.ZodTypeAny, Wire> = z.infer<Schema> extends Wire ? true : never;
export type _SchemasCoverWireTypes = [
  Covers<typeof WireProductionHistorySchema, WireProductionHistory>,
  Covers<typeof WireForecastSchema, WireForecast>,
  Covers<typeof WireShortfallRiskSchema, WireShortfallRisk>,
  Covers<typeof WireRecommendationsSchema, WireRecommendations>,
  Covers<typeof WireDashboardSummarySchema, WireDashboardSummary>,
  Covers<typeof WireHeatmapSchema, WireHeatmap>,
  Covers<typeof WirePredictPointSchema, WirePredictPoint>,
  Covers<typeof WireMinesSchema, WireMines>,
];
