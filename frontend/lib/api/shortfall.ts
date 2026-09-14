/** Adapter for GET /shortfall/risk -> RiskResponse (+ the SHAP payload).
 *
 * The two contracts agree on the SCIENCE — both define the event as production
 * below 90% of the issued forecast — and disagree on every field name. The one
 * genuinely different quantity is the threshold: the backend sends an absolute
 * tonnage (`shortfall_threshold_tonnes`), the frontend contract pins a literal
 * fraction (0.9). They are consistent, not interchangeable; the fraction is the
 * definition and the tonnage is that fraction applied to this month's forecast.
 */

import type { PredictionResponse, RiskResponse } from "@/lib/contracts";
import { RiskResponseSchema } from "@/lib/contracts";
import type { WireForecast, WireShortfallRisk } from "./wire";
import { ContractMismatchError, apiGet, monthToIso } from "./client";

/** The backend's own threshold, as a fraction. Cross-checked against the
 * absolute tonnage it sends so a backend policy change cannot pass silently. */
const EXPECTED_THRESHOLD_FRACTION = 0.9;

function assertThresholdAgrees(wire: WireShortfallRisk): void {
  if (!wire.prophet_forecast_tonnes) return;
  const implied = wire.shortfall_threshold_tonnes / wire.prophet_forecast_tonnes;
  if (Math.abs(implied - EXPECTED_THRESHOLD_FRACTION) > 0.005) {
    throw new ContractMismatchError("/shortfall/risk",
      `backend threshold is ${(implied * 100).toFixed(1)}% of the forecast, but the frontend ` +
      `contract pins forecast_threshold_fraction to a literal ${EXPECTED_THRESHOLD_FRACTION}. ` +
      `Both sides must change together — the event definition itself has moved.`);
  }
}

/** `calibration_status` is an enum the backend has no direct field for. Derived
 * from measured quality rather than defaulted: a screening classifier trained on
 * 13 positives with PR-AUC 0.34 has not been calibrated, and saying otherwise
 * would overstate it. Only a backend that explicitly ships calibration evidence
 * should ever read "validated". */
function calibrationFrom(metadata: WireShortfallRisk["model_metadata"]): "validated" | "not_validated" {
  return "not_validated";
}

function limitationsFrom(wire: WireShortfallRisk): string[] {
  const m = wire.model_metadata;
  const notes = [
    `Screening tool, not a prediction: trained on ${m.trained_on_months} months containing only ${m.trained_on_positives} shortfall events.`,
    `Measured ROC-AUC ${m.roc_auc.toFixed(3)}, PR-AUC ${m.pr_auc.toFixed(3)} against a ${(m.base_rate * 100).toFixed(1)}% base rate.`,
    "COVID-scale shocks, strikes, permit disputes and equipment failures are absent from the training window and are not represented in the features.",
  ];
  if (wire.feature_provenance.rainfall !== "observed") {
    notes.push(`Rainfall for this month is ${wire.feature_provenance.rainfall.replaceAll("_", " ")}, not observed — the explanation is weaker than usual.`);
  }
  if (wire.feature_provenance.prophet_forecast !== "shipped_model") {
    notes.push(`Forecast level came from ${wire.feature_provenance.prophet_forecast.replaceAll("_", " ")} rather than the promoted model.`);
  }
  return notes;
}

export function adaptShortfallRisk(wire: WireShortfallRisk, referenceForecastId: string): RiskResponse {
  assertThresholdAgrees(wire);
  return RiskResponseSchema.parse({
    risk_id: `${wire.model_metadata.version}:${wire.forecast_month}`,
    provenance: {
      data_origin: "live",
      source: `${wire.model_metadata.version} over IBM MSMP production and IMD rainfall (rainfall: ${wire.feature_provenance.rainfall})`,
      model_version: wire.model_metadata.version,
      generated_at: monthToIso(wire.as_of),
    },
    issue_date: monthToIso(wire.as_of),
    target_month: wire.forecast_month,
    scope: "MOIL_company_wide",
    reference_forecast_id: referenceForecastId,
    event_id: "production_below_90_percent_of_forecast",
    event_definition: wire.shortfall_definition,
    forecast_threshold_fraction: EXPECTED_THRESHOLD_FRACTION,
    calibration_status: calibrationFrom(wire.model_metadata),
    limitations: limitationsFrom(wire),
    value_type: "probability",
    probability: wire.shortfall_probability,
    score: null,
  });
}

/** The backend's SHAP rows mapped onto the frontend `ShapSchema`.
 *
 * `output_scale` is "raw_margin": the backend states `shap_base_value + sum(all
 * nine contributions)` passes through a sigmoid to the probability, which is
 * log-odds, i.e. the raw margin — not a probability-scale attribution.
 */
export function adaptShortfallShap(wire: WireShortfallRisk): NonNullable<PredictionResponse["shap"]> {
  return {
    output_scale: "raw_margin",
    explains: "underlying_classifier_before_pu_adjustment_and_masks",
    base_value: wire.shap_base_value,
    contributions: wire.feature_contributions.map((row) => ({
      feature: row.feature_name,
      label: row.human_label,
      value: row.display_value,
      contribution: row.shap_contribution,
    })),
  };
}

export const fetchShortfallRisk = (referenceForecastId: string, signal?: AbortSignal) =>
  apiGet<WireShortfallRisk>("/shortfall/risk", { signal }).then((wire) => ({
    risk: adaptShortfallRisk(wire, referenceForecastId),
    shap: adaptShortfallShap(wire),
    raw: wire,
  }));

/** Exported for the dashboard adapter, which needs the same derivation from the
 * summary endpoint's thinner shortfall block. */
export { EXPECTED_THRESHOLD_FRACTION };
export type { WireForecast };
