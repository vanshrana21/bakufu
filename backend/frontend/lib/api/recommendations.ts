/** Adapter for GET /recommendations and /recommendations/scenario/{month}.
 *
 * The largest contract gap in the project. The backend rules engine emits a
 * recommendation CARD; the frontend contract models a reviewable ACTION RECORD.
 * The backend has no review lifecycle at all — no `review_status`, no reviewer,
 * no persistence, and no write endpoint.
 *
 * That gap is resolved in the only direction that is true: every live card maps
 * to `review_status: "proposed"` with both audit fields null. Nothing has been
 * reviewed, because nothing CAN be reviewed yet. `ActionResponseSchema`'s
 * superRefine enforces exactly that pairing, so the contract already refuses to
 * let a fabricated approval through.
 */

import type { ActionResponse } from "@/lib/contracts";
import { ActionResponseSchema } from "@/lib/contracts";
import type { WireRecommendation, WireRecommendations } from "./wire";
import { apiGet, toIsoTimestamp } from "./client";

/** One row of the review register. `owner` and `target_date` are nullable
 * because the backend supplies neither — the fixture's "Planning / 2026-09-15"
 * values are illustrative, and inventing them from live data would present an
 * unassigned proposal as an assigned commitment. */
export interface RegisterRow {
  action: ActionResponse;
  priority: string;
  owner: string | null;
  target_date: string | null;
}

const titleCase = (value: string) => value.charAt(0).toUpperCase() + value.slice(1);

/** The backend does not send a rule version. Saying so is better than inventing
 * one — `rule_version` is required and non-empty, so it has to say something. */
const RULE_VERSION = "unversioned";

function clausesFrom(card: WireRecommendation): ActionResponse["trigger_condition"]["clauses"] {
  // The engine's actual gate is "this feature's SHAP contribution is positive",
  // i.e. it argues FOR a shortfall. That is the condition being reported, so it
  // is the condition the clause states — observed = the contribution, threshold
  // = 0. The feature's own value (7.1 mm, +11.7%) carries no threshold in the
  // engine and is surfaced as evidence instead of being dressed up as one.
  if (card.triggered_by.length === 0) {
    return [{
      feature: card.driver,
      operator: "gt" as const,
      observed: card.driver_label,
      threshold: "positive SHAP contribution",
      unit: null,
    }];
  }
  return card.triggered_by.map((trigger) => ({
    feature: trigger.signal,
    operator: "gt" as const,
    observed: trigger.shap_contribution,
    threshold: 0,
    unit: "SHAP log-odds",
  }));
}

function evidenceFrom(card: WireRecommendation): ActionResponse["evidence"] {
  const rows = card.triggered_by.map((trigger) => ({
    label: `${trigger.signal.replaceAll("_", " ")} = ${trigger.display_value} · ${card.driver_label}`,
    reference: trigger.signal,
  }));
  if (card.equipment_referenced.length > 0) {
    rows.push({
      label: `Fleet referenced: ${card.equipment_referenced.map((item) => item.replaceAll("_", " ")).join(", ")} (documented MOIL vocabulary)`,
      reference: `fleet:${card.action_type}`,
    });
  }
  return rows.length > 0 ? rows : [{ label: `${card.driver_label} · no numeric trigger supplied`, reference: card.driver }];
}

export function adaptRecommendation(
  card: WireRecommendation,
  wire: WireRecommendations,
  options: { linkedRiskId: string | null; modelVersion: string },
): ActionResponse {
  const evaluatedAt = toIsoTimestamp(wire.generated_at);
  return ActionResponseSchema.parse({
    action_id: card.id,
    provenance: {
      data_origin: "live",
      source: `Deterministic rules engine over ${options.modelVersion} SHAP output for ${wire.context.forecast_month}`,
      model_version: options.modelVersion,
      generated_at: evaluatedAt,
    },
    rule_id: card.id,
    rule_version: RULE_VERSION,
    title: card.title,
    recommendation: card.rationale,
    scope: "MOIL_company_wide",
    trigger_condition: {
      summary: `${card.driver_label} is the ${wire.context.drivers_ranked[0]?.driver === card.driver ? "leading" : "contributing"} risk driver at p=${wire.context.shortfall_probability.toFixed(4)} for ${wire.context.forecast_month}.`,
      evaluated_at: evaluatedAt,
      clauses: clausesFrom(card),
    },
    // The backend has no review workflow, so nothing is reviewed. Both audit
    // fields stay null; the schema rejects any other combination.
    review_status: "proposed",
    domain_validation: "pending",
    linked_risk_id: options.linkedRiskId,
    evidence: evidenceFrom(card),
    reviewed_by: null,
    reviewed_at: null,
  });
}

export interface RecommendationsResult {
  rows: RegisterRow[];
  /** Present when the engine returns no cards — e.g. low risk. Render it; an
   * empty register with no explanation reads as a loading failure. */
  message: string | null;
  footnotes: string[];
  probability: number;
  riskLevel: string;
  forecastMonth: string;
  coverageComplete: boolean;
  actionTypesOmitted: string[];
  scenario: { month: string; actualShortfall: boolean } | null;
}

export function adaptRecommendations(
  wire: WireRecommendations,
  options: { linkedRiskId: string | null; modelVersion: string },
): RecommendationsResult {
  return {
    rows: wire.recommendations.map((card) => ({
      action: adaptRecommendation(card, wire, options),
      priority: titleCase(card.priority),
      owner: null,
      target_date: null,
    })),
    message: wire.context.message ?? null,
    footnotes: wire.context.footnotes ?? [],
    probability: wire.context.shortfall_probability,
    riskLevel: wire.context.risk_level,
    forecastMonth: wire.context.forecast_month,
    coverageComplete: wire.coverage_complete,
    actionTypesOmitted: wire.action_types_omitted ?? [],
    scenario: wire.context.scenario_month
      ? { month: wire.context.scenario_month, actualShortfall: Boolean(wire.context.actual_shortfall) }
      : null,
  };
}

export const fetchRecommendations = (
  options: { mineName?: string; limit?: number; linkedRiskId: string | null; modelVersion: string; signal?: AbortSignal },
) =>
  apiGet<WireRecommendations>("/recommendations", {
    query: { mine_name: options.mineName, limit: options.limit },
    signal: options.signal,
  }).then((wire) => adaptRecommendations(wire, options));

/** Replays a real historical shortfall month. Useful for the demo, because the
 * current month usually scores low and correctly returns zero cards. */
export const fetchScenarioRecommendations = (
  month: string,
  options: { mineName?: string; limit?: number; linkedRiskId: string | null; modelVersion: string; signal?: AbortSignal },
) =>
  apiGet<WireRecommendations>(`/recommendations/scenario/${encodeURIComponent(month)}`, {
    query: { mine_name: options.mineName, limit: options.limit },
    signal: options.signal,
  }).then((wire) => adaptRecommendations(wire, options));
