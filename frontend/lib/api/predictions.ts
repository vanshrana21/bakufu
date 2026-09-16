import type { MaskMode, PredictionResponse } from "@/lib/contracts";
import { PredictionResponseSchema } from "@/lib/contracts";
import { DEMO_SITES, buildPredictionFixture, type SiteFixture } from "@/fixtures/predictions";
import type { WirePredictPoint } from "./wire";
import { ApiRequestError, ContractMismatchError, LIVE_MODE, PREDICT_POINT_TIMEOUT_MS, apiPost } from "./client";

export interface PredictionClient {
  predict(siteId: string, mask: MaskMode, signal: AbortSignal): Promise<PredictionResponse>;
}

function delay(ms: number, signal: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal.aborted) { reject(new DOMException("Aborted", "AbortError")); return; }
    const abort = () => { clearTimeout(timer); reject(new DOMException("Aborted", "AbortError")); };
    const timer = setTimeout(() => { signal.removeEventListener("abort", abort); resolve(); }, ms);
    signal.addEventListener("abort", abort, { once: true });
  });
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

/** Live scores on a SYNTHETIC asset inventory.
 *
 * The backend scores coordinates; it has no waste-dump or slag inventory, and
 * neither does the project. The asset identity, buffer membership and scope
 * gating therefore still come from the fixture, and only the numbers are live.
 * `provenance.source` states that split, because a "live" badge over a
 * synthetic inventory would be the most misleading thing this screen could do.
 */
function composeLive(site: SiteFixture, wire: WirePredictPoint, mask: MaskMode): PredictionResponse {
  const allNull = Object.values(wire.features_extracted).every((value) => value === null);
  const outsideFootprint = allNull;

  const base = {
    prediction_id: wire.prediction_id === null ? `live:${site.id}:${mask}` : String(wire.prediction_id),
    provenance: {
      data_origin: "live" as const,
      source: `Score from ${wire.model_version} at ${wire.lat.toFixed(4)}, ${wire.lon.toFixed(4)}. Asset identity and 5 km buffer membership are synthetic fixture metadata; no verified waste inventory exists.`,
      model_version: wire.model_version,
      generated_at: new Date().toISOString(),
    },
    asset: null,
    location: site.location,
    validated_scope: "Sausar Belt" as const,
    mask_requested: mask,
  };

  // Inside the belt but outside the imagery footprint: every feature came back
  // null. The model produced no evidence, so no score is surfaced. This is the
  // documented Kandri/Beldongri case.
  if (outsideFootprint) {
    return PredictionResponseSchema.parse({
      ...base,
      scope_status: "unknown",
      scope_reason: "Inside the Sausar Belt, but outside the model's current imagery footprint.",
      raw_score: null, final_score: null, mask_applied: "none", mask_results: [], shap: null,
      interpretation: "Every feature for this location was null, so no score is produced. This is missing data, not an absence of manganese.",
    });
  }

  // Mask results are derived from the backend's decision, so they are only
  // truthful for the mask the backend actually applied.
  if (wire.mask_applied !== mask) {
    throw new ContractMismatchError("/predict/point", `requested mask "${mask}" but the backend applied "${wire.mask_applied}"`);
  }
  const maskResults = maskResultsFrom(wire, mask);
  const excluded = maskResults.some((result) => result.outcome === "excluded");
  return PredictionResponseSchema.parse({
    ...base,
    scope_status: "in_scope",
    scope_reason: "Inside the Sausar Belt, the model's validated geographic scope.",
    raw_score: wire.raw_score ?? wire.prospectivity_score,
    final_score: excluded ? 0 : (wire.final_score ?? wire.raw_score ?? wire.prospectivity_score),
    mask_applied: mask,
    mask_results: maskResults,
    interpretation: excluded
      ? "A screening mask excluded this location. The zero is a policy result, not a model score — the raw score beside it is what the model actually produced."
      : `Screening score ${(wire.raw_score ?? wire.prospectivity_score).toFixed(2)} on a 0–0.99 scale. This is a screening index, not a recovery probability or an ore quantity.`,
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
  });
}

export const predictionClient: PredictionClient = {
  async predict(siteId, mask, signal) {
    const site = DEMO_SITES.find((candidate) => candidate.id === siteId);
    if (!site) throw new Error("No fixture exists for this location. A live point-query API is required.");

    // SAUSAR SCOPE GATE: runs BEFORE inference, in both modes. An out-of-scope
    // location never reaches the model, so no score can exist to be shown.
    if (site.scope_status !== "in_scope" || !site.location) {
      return buildPredictionFixture(siteId, mask);
    }
    if (!LIVE_MODE) {
      await delay(250, signal);
      return PredictionResponseSchema.parse(buildPredictionFixture(siteId, mask));
    }

    try {
      // `mask` is a QUERY parameter on the backend; PredictPointIn carries only
      // lat/lon, so a mask in the body is silently dropped and "none" applied.
      const wire = await apiPost<WirePredictPoint>(
        "/predict/point",
        { lat: site.location.latitude, lon: site.location.longitude },
        { signal, query: { mask }, timeoutMs: PREDICT_POINT_TIMEOUT_MS },
      );
      return composeLive(site, wire, mask);
    } catch (error) {
      // A 404 here is the backend's honest "outside the imagery footprint"
      // answer, not a failure. Surface it as unknown scope with null scores.
      if (error instanceof ApiRequestError && error.status === 404) {
        return PredictionResponseSchema.parse({
          prediction_id: `live:${site.id}:${mask}`,
          provenance: {
            data_origin: "live" as const,
            source: "Backend reports this location falls outside the available imagery footprint.",
            model_version: "unavailable",
            generated_at: new Date().toISOString(),
          },
          asset: null,
          location: site.location,
          validated_scope: "Sausar Belt" as const,
          scope_status: "unknown",
          scope_reason: "Outside the available imagery footprint.",
          raw_score: null, final_score: null,
          mask_requested: mask, mask_applied: "none", mask_results: [], shap: null,
          interpretation: error.message,
        });
      }
      throw error;
    }
  },
};
