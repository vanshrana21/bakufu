/** Adapter for POST /predict/point: the evidence behind one coordinate.
 *
 * The Explorer explains two kinds of place, an operating MOIL mine and one of
 * the model's greenfield targets. Both are coordinates, so one call serves
 * both, under whichever mask the Explorer has active - which is also why the
 * mask toggles change what the inspector reports, not just the surface.
 */

import type { MaskMode, PredictionResponse } from "@/lib/contracts";
import { PredictionResponseSchema } from "@/lib/contracts";
import type { WirePredictPoint } from "./wire";
import { ApiRequestError, ContractMismatchError, PREDICT_POINT_TIMEOUT_MS, apiPost } from "./client";
import { parseWire, WirePredictPointSchema } from "./wire-schemas";

export interface Coordinate {
  latitude: number;
  longitude: number;
}

/** Which mask results the contract expects to be present for a given request. */
const activeMasks = (mask: MaskMode): Array<"geological" | "occurrence_buffer"> =>
  mask === "both" ? ["geological", "occurrence_buffer"] : mask === "none" ? [] : [mask];

/** Which masks the backend's decision blames for an exclusion.
 *
 * Under `mask=both` the backend evaluates basement and buffer separately and
 * names the test that failed, so the exclusion is attributed rather than
 * duplicated across both masks. An older backend that still reports the
 * conjunction lands in `null`, and both masks then carry the exclusion with the
 * text saying the attribution was not available.
 */
function blamedBy(decision: string): Array<"geological" | "occurrence_buffer"> | null {
  if (decision === "masked_out_not_in_basement") return ["geological"];
  if (decision === "masked_out_not_in_buffer") return ["occurrence_buffer"];
  if (decision === "masked_out_neither_basement_nor_buffer") return ["geological", "occurrence_buffer"];
  return null;
}

/** The backend returns ONE `mask_decision` string and the frontend contract
 * requires one result per active mask, so the decision is mapped back onto the
 * masks it names.
 */
function maskResultsFrom(wire: WirePredictPoint, mask: MaskMode): PredictionResponse["mask_results"] {
  const masks = activeMasks(mask);
  if (masks.length === 0) return [];
  const raw = wire.raw_score;
  const final = wire.final_score;
  const excluded = final === 0 && raw !== null && raw > 0;
  const decision = wire.mask_decision ?? "";
  const combined = decision && decision !== "n/a" ? decision.replaceAll("_", " ") : "no decision reported";
  const blamed = excluded && masks.length > 1 ? blamedBy(decision) : null;
  const unattributed = masks.length > 1 && excluded && blamed === null;

  return masks.map((name) => ({
    mask: name,
    outcome: excluded && (blamed === null || blamed.includes(name)) ? ("excluded" as const) : ("passed" as const),
    reason: unattributed
      ? `Excluded under the combined geological ∩ occurrence-buffer policy. The backend reports one decision for both masks ("${combined}") and does not attribute the exclusion to either one individually.`
      : excluded && blamed !== null && !blamed.includes(name)
        ? `Passed this mask; the exclusion came from the other one. Backend decision: "${combined}".`
      : excluded
        ? `Excluded by this mask. Backend decision: "${combined}".`
        : `Passed this mask; the screened score equals the raw score. Backend decision: "${combined}".`,
    source: name === "geological"
      ? "Macrostrat 1:5M Precambrian basement proxy; boundaries are tens of km coarse."
      : "Union of per-point 5 km buffers around confirmed manganese occurrences.",
  }));
}

/** No score, and the reason there is none. A missing measurement must never
 * reach the screen as a zero. */
function unscored(location: Coordinate, mask: MaskMode, source: string, reason: string, interpretation: string): PredictionResponse {
  return PredictionResponseSchema.parse({
    prediction_id: `live:${location.latitude.toFixed(5)},${location.longitude.toFixed(5)}:${mask}`,
    provenance: { data_origin: "live", source, model_version: "unavailable", generated_at: new Date().toISOString() },
    asset: null,
    location,
    validated_scope: "Sausar Belt",
    scope_status: "unknown",
    scope_reason: reason,
    raw_score: null, final_score: null, mask_requested: mask, mask_applied: "none", mask_results: [],
    shap: null, model_margin: null, raw_probability: null,
    interpretation,
  });
}

/** Maps one /predict/point response onto the frontend contract. Pure, so the
 * scientific rules it enforces are tested without a backend. */
export function adaptPointPrediction(wire: WirePredictPoint, mask: MaskMode, location: Coordinate): PredictionResponse {
  // Inside the belt but outside the imagery footprint: every feature came back
  // null. The model produced no evidence, so no score is surfaced.
  if (Object.values(wire.features_extracted).every((value) => value === null)) {
    return unscored(location, mask,
      `Queried ${wire.model_version} at ${wire.lat.toFixed(4)}, ${wire.lon.toFixed(4)}; no feature had a value there.`,
      "Inside the Sausar Belt, but outside the model's current imagery footprint.",
      "Every feature for this location was null, so no score is produced. This is missing data, not an absence of manganese.");
  }

  // Mask results are derived from the backend's decision, so they are only
  // truthful for the mask the backend actually applied.
  if (wire.mask_applied !== mask) {
    throw new ContractMismatchError("/predict/point", `requested mask "${mask}" but the backend applied "${wire.mask_applied}"`);
  }
  const maskResults = maskResultsFrom(wire, mask);
  const excluded = maskResults.some((result) => result.outcome === "excluded");
  const raw = wire.raw_score ?? wire.prospectivity_score;
  return PredictionResponseSchema.parse({
    prediction_id: wire.prediction_id === null
      ? `live:${location.latitude.toFixed(5)},${location.longitude.toFixed(5)}:${mask}`
      : String(wire.prediction_id),
    provenance: {
      data_origin: "live",
      source: `Scored by ${wire.model_version} at ${wire.lat.toFixed(4)}, ${wire.lon.toFixed(4)}.`,
      model_version: wire.model_version,
      generated_at: new Date().toISOString(),
    },
    asset: null,
    location,
    validated_scope: "Sausar Belt",
    scope_status: "in_scope",
    scope_reason: "Inside the Sausar Belt, the model's validated geographic scope.",
    raw_score: raw,
    final_score: excluded ? 0 : (wire.final_score ?? raw),
    mask_requested: mask,
    mask_applied: mask,
    mask_results: maskResults,
    interpretation: excluded
      ? "A screening mask excluded this location. The zero is a policy result, not a model score — the raw score beside it is what the model actually produced."
      : `Screening index ${raw.toFixed(2)} on a 0–0.99 scale for this pixel. Values move sharply within a kilometre, so read the surface around it too. Not a recovery probability or an ore quantity.`,
    shap: wire.shap_top5.length === 0 ? null : {
      output_scale: "raw_margin",
      explains: "underlying_classifier_before_pu_adjustment_and_masks",
      base_value: wire.shap_base_value ?? 0,
      contributions: wire.shap_top5.map((row) => ({
        feature: row.feature,
        label: row.feature.replaceAll("_", " "),
        value: row.actual_value,
        contribution: row.shap_value,
      })),
    },
    model_margin: typeof wire.model_margin === "number" ? wire.model_margin : null,
    raw_probability: typeof wire.raw_probability === "number" ? wire.raw_probability : null,
  });
}

/** The backend refuses to serve a score it cannot write to its audit table
 * (503). Said in words an operator can act on: the model is fine, the database
 * connection is not. */
export function explainFailure(error: unknown): string {
  if (error instanceof ApiRequestError && error.status === 503 && /audit record/i.test(error.message)) {
    return "The model scored this point, but the backend will not serve a score it cannot audit, and its database is unreachable. " +
      "Restore DATABASE_URL in backend/.env and restart the backend.";
  }
  return error instanceof Error ? error.message : "Scoring failed.";
}

/** Score, mask outcomes and SHAP drivers at one coordinate, live. */
export async function explainPoint(location: Coordinate, mask: MaskMode, signal: AbortSignal): Promise<PredictionResponse> {
  try {
    // `mask` is a QUERY parameter on the backend; PredictPointIn carries only
    // lat/lon, so a mask in the body is silently dropped and "none" applied.
    const raw = await apiPost<unknown>(
      "/predict/point",
      { lat: location.latitude, lon: location.longitude },
      { signal, query: { mask }, timeoutMs: PREDICT_POINT_TIMEOUT_MS },
    );
    return adaptPointPrediction(parseWire(WirePredictPointSchema, raw, "/predict/point"), mask, location);
  } catch (error) {
    // A 404 here is the backend's honest "no imagery at this coordinate", not a
    // failure. Surface it as unknown scope with null scores.
    if (error instanceof ApiRequestError && error.status === 404) {
      return unscored(location, mask,
        "Backend reports no Sentinel-2 imagery at this coordinate.",
        "Outside the available imagery footprint.",
        "The served mosaic has no pixels here, so no score is produced. That is missing data, not an absence of manganese.");
    }
    throw error;
  }
}
