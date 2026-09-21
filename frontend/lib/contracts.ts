import { z } from "zod";

/** Proposed frontend v1 contract, NOT a claim about the current FastAPI wire schema.
 * The project document specifies capabilities, not complete response bodies.
 * Adapt actual backend responses at lib/api; never silently fabricate fields.
 */
const Nonempty = z.string().trim().min(1);
const Finite = z.number().finite();
const Fraction = Finite.min(0).max(1);
const ProspectivityScore = Finite.min(0).max(0.99); // Documented v6 cap.
const Timestamp = z.string().datetime({ offset: true });
export const MonthSchema = z.string().regex(/^\d{4}-(0[1-9]|1[0-2])$/);
export const MaskModeSchema = z.enum(["none", "geological", "occurrence_buffer", "both"]);
export type MaskMode = z.infer<typeof MaskModeSchema>;
export const ScopeStatusSchema = z.enum(["in_scope", "out_of_scope", "unknown"]);

export const ProvenanceSchema = z.object({
  data_origin: z.enum(["fixture", "live"]),
  source: Nonempty,
  model_version: Nonempty,
  generated_at: Timestamp,
});
export const LocationSchema = z.object({
  longitude: Finite.min(-180).max(180),
  latitude: Finite.min(-90).max(90),
});
export const AssetSchema = z.object({
  id: Nonempty,
  name: Nonempty,
  asset_type: z.enum(["historical_waste_dump", "slag_heap", "diagnostic_point", "place"]),
  inventory_status: z.enum(["synthetic", "documented"]),
  assay_status: z.enum(["pending", "available", "not_applicable"]),
  occurrence_buffer_membership: z.enum(["inside", "outside", "unknown"]),
});
const MaskResultSchema = z.object({
  mask: z.enum(["geological", "occurrence_buffer"]),
  outcome: z.enum(["passed", "excluded", "unknown"]),
  reason: Nonempty,
  source: Nonempty,
});
export const ShapSchema = z.object({
  output_scale: z.enum(["raw_margin", "probability"]),
  explains: z.literal("underlying_classifier_before_pu_adjustment_and_masks"),
  base_value: Finite,
  contributions: z.array(z.object({
    // Null where the feature had no value at this point. Displayed as such:
    // substituting zero would show a measurement that was never taken.
    feature: Nonempty, label: Nonempty, value: z.union([Finite, Nonempty]).nullable(), contribution: Finite,
  })).min(1),
});

export const PredictionResponseSchema = z.object({
  prediction_id: Nonempty,
  provenance: ProvenanceSchema,
  /** Fixture mode may provide demo inventory context; live scoring does not. */
  asset: AssetSchema.nullable(),
  location: LocationSchema.nullable(),
  validated_scope: z.literal("Sausar Belt"),
  scope_status: ScopeStatusSchema,
  scope_reason: Nonempty,
  raw_score: ProspectivityScore.nullable(), // PU-adjusted, capped, BEFORE masks.
  final_score: ProspectivityScore.nullable(),
  mask_requested: MaskModeSchema,
  mask_applied: MaskModeSchema, // none when no assessment can be performed.
  mask_results: z.array(MaskResultSchema),
  interpretation: Nonempty,
  shap: ShapSchema.nullable(),
  /** The classifier's log-odds and probability before the Elkan-Noto division
   * and the 0.99 cap (backend contract v1.10). Strong locations all read 0.99
   * once capped; these keep the model's own ordering visible. Null when the
   * backend predates v1.10 or produced no score. */
  model_margin: Finite.nullable(),
  raw_probability: Fraction.nullable(),
}).strict().superRefine((r, ctx) => {
  const issue = (path: string, message: string) =>
    ctx.addIssue({ code: z.ZodIssueCode.custom, path: [path], message });
  if (r.scope_status !== "in_scope") {
    if (r.raw_score !== null || r.final_score !== null || r.shap !== null ||
        r.model_margin !== null || r.raw_probability !== null)
      issue("scope_status", "Outside/unknown scope must not contain model scores or SHAP.");
    if (r.mask_applied !== "none" || r.mask_results.length)
      issue("mask_applied", "No masks are applied to an unassessed location.");
    return;
  }
  if (!r.location || r.raw_score === null) issue("raw_score", "In-scope predictions require a location and raw score.");
  if (r.mask_applied !== r.mask_requested) issue("mask_applied", "Evaluated policy must match the request.");
  const expected = r.mask_applied === "both" ? ["geological", "occurrence_buffer"]
    : r.mask_applied === "none" ? [] : [r.mask_applied];
  if (r.mask_results.length !== expected.length || expected.some((m) => r.mask_results.filter((x) => x.mask === m).length !== 1))
    issue("mask_results", "Provide exactly one result for each active mask.");
  const excluded = r.mask_results.some((m) => m.outcome === "excluded");
  const unknown = r.mask_results.some((m) => m.outcome === "unknown");
  if (excluded && r.final_score !== 0) issue("final_score", "An exclusion must produce zero screened score.");
  if (!excluded && unknown && r.final_score !== null) issue("final_score", "An unresolved gate cannot produce a screened score.");
  if (!excluded && !unknown && r.final_score !== r.raw_score)
    issue("final_score", "Passing binary masks preserve the raw score.");
});
export type PredictionResponse = z.infer<typeof PredictionResponseSchema>;

const ForecastPointSchema = z.object({
  month: MonthSchema,
  point_estimate: Finite.nonnegative(),
  lower_bound: Finite.nonnegative().nullable(),
  upper_bound: Finite.nonnegative().nullable(),
}).superRefine((p, ctx) => {
  if ((p.lower_bound === null) !== (p.upper_bound === null) ||
      (p.lower_bound !== null && p.upper_bound !== null &&
        (p.lower_bound > p.point_estimate || p.point_estimate > p.upper_bound)))
    ctx.addIssue({ code: z.ZodIssueCode.custom, message: "Bounds must be paired and lower ≤ estimate ≤ upper." });
});
export const ForecastResponseSchema = z.object({
  forecast_id: Nonempty,
  provenance: ProvenanceSchema,
  scope: z.literal("MOIL_company_wide"),
  unit: z.literal("tonnes"),
  issue_date: Timestamp,
  data_cutoff: Timestamp,
  last_observed_month: MonthSchema,
  horizon_months: z.union([z.literal(1), z.literal(3), z.literal(6), z.literal(12)]),
  interval: z.object({ level: Fraction.gt(0).lt(1), kind: z.enum(["prediction", "confidence"]), method: Nonempty }).nullable(),
  points: z.array(ForecastPointSchema).min(1).max(12),
}).strict().superRefine((r, ctx) => {
  const error = (message: string) => ctx.addIssue({ code: z.ZodIssueCode.custom, message });
  if (Date.parse(r.data_cutoff) > Date.parse(r.issue_date)) error("Data cutoff must not follow forecast issue date.");
  if (r.points.length !== r.horizon_months) error("Point count must equal horizon.");
  let previous = r.last_observed_month;
  for (const p of r.points) {
    const expected = new Date(`${previous}-01T00:00:00Z`);
    expected.setUTCMonth(expected.getUTCMonth() + 1);
    if (p.month !== expected.toISOString().slice(0, 7)) error("Forecast months must be consecutive after the last observation.");
    if ((r.interval === null) !== (p.lower_bound === null)) error("Interval metadata and bounds must agree.");
    previous = p.month;
  }
});
export type ForecastResponse = z.infer<typeof ForecastResponseSchema>;

const RiskBase = z.object({
  risk_id: Nonempty,
  provenance: ProvenanceSchema,
  issue_date: Timestamp,
  target_month: MonthSchema,
  scope: z.literal("MOIL_company_wide"),
  reference_forecast_id: Nonempty,
  event_id: z.literal("production_below_90_percent_of_forecast"),
  event_definition: Nonempty,
  forecast_threshold_fraction: z.literal(0.9),
  calibration_status: z.enum(["validated", "not_validated"]),
  limitations: z.array(Nonempty).min(1),
});
export const RiskResponseSchema = z.discriminatedUnion("value_type", [
  RiskBase.extend({ value_type: z.literal("probability"), probability: Fraction, score: z.null() }).strict(),
  RiskBase.extend({
    value_type: z.literal("score"), probability: z.null(),
    score: z.object({ value: Finite, minimum: Finite, maximum: Finite, higher_means_more_risk: z.boolean() })
      .refine((s) => s.minimum < s.maximum && s.value >= s.minimum && s.value <= s.maximum, "Invalid score range."),
  }).strict(),
]);
export type RiskResponse = z.infer<typeof RiskResponseSchema>;

export const ActionResponseSchema = z.object({
  action_id: Nonempty,
  provenance: ProvenanceSchema,
  rule_id: Nonempty,
  rule_version: Nonempty,
  title: Nonempty,
  recommendation: Nonempty,
  scope: z.literal("MOIL_company_wide"),
  trigger_condition: z.object({
    summary: Nonempty,
    evaluated_at: Timestamp,
    clauses: z.array(z.object({
      feature: Nonempty,
      operator: z.enum(["lt", "lte", "gt", "gte", "eq"]),
      observed: z.union([Finite, Nonempty, z.boolean()]),
      threshold: z.union([Finite, Nonempty, z.boolean()]),
      unit: Nonempty.nullable(),
    })).min(1),
  }),
  review_status: z.enum(["proposed", "reviewed", "dismissed"]),
  domain_validation: z.enum(["pending", "validated"]),
  linked_risk_id: Nonempty.nullable(),
  evidence: z.array(z.object({ label: Nonempty, reference: Nonempty })).min(1),
  reviewed_by: Nonempty.nullable(),
  reviewed_at: Timestamp.nullable(),
}).strict().superRefine((r, ctx) => {
  const hasReview = r.reviewed_by !== null && r.reviewed_at !== null;
  if ((r.review_status !== "proposed" && !hasReview) ||
      (r.review_status === "proposed" && (r.reviewed_by !== null || r.reviewed_at !== null)))
    ctx.addIssue({ code: z.ZodIssueCode.custom, message: "Review state must agree with audit fields." });
});
export type ActionResponse = z.infer<typeof ActionResponseSchema>;

/* ---------------------------------------------------------------------------
 * Mine fleet and greenfield targets (backend contract v1.9–v1.10).
 * ------------------------------------------------------------------------- */

/** What the model reads at one cited coordinate. `value` is the served score,
 * capped at 0.99; `raw_probability` and `margin` are the classifier's own output
 * before the Elkan-Noto adjustment and the cap, which is what still separates
 * two locations that both read 0.99. */
export const MineScoreSchema = z.object({
  value: ProspectivityScore,
  raw_probability: Finite.nullable(),
  margin: Finite.nullable(),
  drivers: z.array(z.object({ label: Nonempty, contribution: Finite, value: Finite.nullable() })),
  model_version: Nonempty,
});
export type MineScore = z.infer<typeof MineScoreSchema>;

export const MineSchema = z.object({
  name: Nonempty,
  state: Nonempty,
  district: Nonempty,
  mine_type: Nonempty,
  location: LocationSchema,
  coordinate: z.object({
    confidence: Nonempty,
    source: Nonempty,
    source_url: z.string().nullable(),
    precision: z.string().nullable(),
    note: z.string().nullable(),
  }),
  equipment: z.array(z.string()),
  capacity_target_tonnes: Finite.nullable(),
  notes: z.string().nullable(),
  score: MineScoreSchema.nullable(),
  /** Why there is no score. Null exactly when a score is present. */
  score_unavailable: z.string().nullable(),
  /** A measured caution specific to this mine, from the score analysis. */
  caveat: z.string().nullable(),
}).superRefine((mine, ctx) => {
  // Either a score or the stated reason there is none. Both null would render
  // as an empty card, which reads as "nothing here" rather than "not measured".
  if ((mine.score === null) === (mine.score_unavailable === null)) {
    ctx.addIssue({ code: z.ZodIssueCode.custom, message: "A mine must carry either a score or the reason it has none." });
  }
});
export type Mine = z.infer<typeof MineSchema>;

export const MineRosterSchema = z.object({
  provenance: ProvenanceSchema,
  counts: z.object({
    total: z.number().int(), underground: z.number().int(), opencast: z.number().int(),
    maharashtra: z.number().int(), madhya_pradesh: z.number().int(),
  }),
  mines: z.array(MineSchema).min(1),
});
export type MineRoster = z.infer<typeof MineRosterSchema>;

/** A mine's identity and cited coordinate, without a score. The Explorer needs
 * ten positions, not ten model runs: scoring every mine to draw a marker would
 * cost ten /predict/point calls (and ten audit rows) on every load. The
 * inspector scores the one that is selected. */
export const MineLocationSchema = z.object({
  name: Nonempty,
  state: Nonempty,
  district: Nonempty,
  mine_type: Nonempty,
  location: LocationSchema,
  /** The researcher's confidence in the cited coordinate, not the model's. */
  coordinate_confidence: Nonempty,
  coordinate_source: Nonempty,
  coordinate_source_url: z.string().nullable(),
  coordinate_note: z.string().nullable(),
}).strict();
export type MineLocation = z.infer<typeof MineLocationSchema>;

export const TargetSchema = z.object({
  id: Nonempty,
  rank: z.number().int().min(1),
  /** "12 km NE of Tirodi": a location a geologist can navigate to. */
  label: Nonempty,
  location: LocationSchema,
  score: ProspectivityScore,
  /** Mean score of the eight neighbouring cells: a coherent anomaly, not a lone pixel. */
  neighbourhood_score: Finite.min(0).max(1),
  nearest_mine: Nonempty,
  km_to_nearest_mine: Finite.min(0),
  bearing_from_mine: z.enum(["N", "NE", "E", "SE", "S", "SW", "W", "NW"]),
  /** Half the longer side of the sub-cell the target was refined to, in
   * metres: the coordinate is good to about ± this along either axis. */
  precision_m: Finite.min(0),
  margin: Finite.nullable(),
  raw_probability: Finite.nullable(),
});
export type Target = z.infer<typeof TargetSchema>;

export const TargetListSchema = z.object({
  provenance: ProvenanceSchema,
  bbox: z.tuple([Finite, Finite, Finite, Finite]),
  candidates_considered: z.number().int().min(0),
  min_separation_km: Finite.min(0),
  /** How the shortlist was ordered. Margins decide when every one arrived;
   * otherwise the shortlist keeps its coherence order and says so. */
  ranking: z.enum(["classifier_margin", "neighbourhood_coherence"]),
  ranking_note: Nonempty,
  targets: z.array(TargetSchema),
});
export type TargetList = z.infer<typeof TargetListSchema>;
