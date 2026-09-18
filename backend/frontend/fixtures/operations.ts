import { ActionResponseSchema, ForecastResponseSchema, RiskResponseSchema } from "@/lib/contracts";

/** Synthetic history for layout testing only. Not MOIL filing observations. */
export const historyFixture = [
  { month: "2026-04", tonnes: 128000 }, { month: "2026-05", tonnes: 135000 },
  { month: "2026-06", tonnes: 129000 }, { month: "2026-07", tonnes: 116000 },
  { month: "2026-08", tonnes: 119000 },
] as const;

const provenance = {
  data_origin: "fixture" as const, source: "Synthetic Phase 3/4 UI data; not measured performance",
  model_version: "mock-only", generated_at: "2026-09-08T00:00:00Z",
};
export const forecastFixture = ForecastResponseSchema.parse({
  forecast_id: "demo-forecast-01", provenance, scope: "MOIL_company_wide", unit: "tonnes",
  issue_date: "2026-09-01T00:00:00Z", data_cutoff: "2026-09-01T00:00:00Z", last_observed_month: "2026-08", horizon_months: 3,
  interval: { level: 0.8, kind: "prediction", method: "Synthetic illustrative bounds" },
  points: [
    { month: "2026-09", point_estimate: 125000, lower_bound: 108000, upper_bound: 142000 },
    { month: "2026-10", point_estimate: 132000, lower_bound: 109000, upper_bound: 155000 },
    { month: "2026-11", point_estimate: 138000, lower_bound: 110000, upper_bound: 166000 },
  ],
});
export const riskFixture = RiskResponseSchema.parse({
  risk_id: "demo-risk-01", provenance, issue_date: "2026-09-01T00:00:00Z", target_month: "2026-09",
  scope: "MOIL_company_wide", reference_forecast_id: forecastFixture.forecast_id,
  event_id: "production_below_90_percent_of_forecast", forecast_threshold_fraction: 0.9,
  event_definition: "September production below 90% of the forecast issued on 1 September 2026.",
  value_type: "probability", probability: 0.32, score: null, calibration_status: "not_validated",
  limitations: ["Synthetic probability for UI development.", "Strikes, permit disputes and equipment failures are not represented in the planned features."],
});
export const actionFixture = ActionResponseSchema.parse({
  action_id: "demo-action-01", provenance, rule_id: "DEMO-R-01", rule_version: "draft",
  title: "Review procurement lead times",
  recommendation: "Ask the planning team to review procurement lead times. This demonstration rule has not been domain-validated.",
  scope: "MOIL_company_wide", domain_validation: "pending", linked_risk_id: riskFixture.risk_id,
  trigger_condition: {
    summary: "Illustrative downside probability exceeds the demonstration review threshold.",
    evaluated_at: "2026-09-08T00:00:00Z",
    clauses: [{ feature: "downside_probability", operator: "gt", observed: 0.32, threshold: 0.3, unit: null }],
  },
  review_status: "proposed", reviewed_by: null, reviewed_at: null,
  evidence: [{ label: "Simulated risk response", reference: riskFixture.risk_id }],
});

/** UI register metadata stays separate from the strict backend ActionResponse. */
export const reviewRegisterFixture = [
  { action: actionFixture, priority: "High", owner: "Planning", target_date: "2026-09-15" },
  { action: ActionResponseSchema.parse({
    ...actionFixture, action_id: "demo-action-02", rule_id: "DEMO-R-02",
    title: "Review water-management readiness",
    recommendation: "Review pumping readiness with operations. No pump-capacity increase is authorized by this demonstration rule.",
    trigger_condition: { ...actionFixture.trigger_condition,
      summary: "Synthetic water-readiness score falls below the demonstration threshold.",
      clauses: [{ feature: "water_readiness_score", operator: "lt", observed: 0.6, threshold: 0.7, unit: null }] },
    evidence: [{ label: "Synthetic readiness scenario; not a measured constraint", reference: "demo-water-01" }],
  }), priority: "High", owner: "Operations", target_date: "2026-09-20" },
  { action: ActionResponseSchema.parse({
    ...actionFixture, action_id: "demo-action-03", rule_id: "DEMO-R-03", linked_risk_id: null,
    title: "Plan waste dump A assay review",
    recommendation: "Request a sampling-plan review before interpreting the screening score as recoverable material. No measured ore is claimed.",
    trigger_condition: { ...actionFixture.trigger_condition,
      summary: "Synthetic dump A exceeds the demonstration screening threshold; assay pending.",
      clauses: [{ feature: "raw_screening_score", operator: "gt", observed: 0.84, threshold: 0.8, unit: null }] },
    evidence: [{ label: "Synthetic waste dump; assay not supplied", reference: "demo-dump-a" }],
  }), priority: "Medium", owner: "Geology", target_date: "2026-09-25" },
  { action: ActionResponseSchema.parse({
    ...actionFixture, action_id: "demo-action-04", rule_id: "DEMO-R-04", linked_risk_id: null,
    title: "Review slag heap B material suitability",
    recommendation: "Review material transfer and environmental requirements. Sausar geological training does not establish slag recoverability.",
    trigger_condition: { ...actionFixture.trigger_condition,
      summary: "Synthetic slag screening score exceeds the demonstration review threshold.",
      clauses: [{ feature: "raw_screening_score", operator: "gt", observed: 0.62, threshold: 0.6, unit: null }] },
    evidence: [{ label: "Synthetic slag inventory; no environmental clearance supplied", reference: "demo-slag-b" }],
  }), priority: "Medium", owner: "Geology / HSE", target_date: "2026-09-30" },
] as const;

export const vitalSignsFixture = {
  latest_production: historyFixture[historyFixture.length - 1]!,
  next_forecast: forecastFixture.points[0]!,
  downside_risk: riskFixture,
  pending_reviews: reviewRegisterFixture.filter(({ action }) => action.review_status === "proposed").length,
};
