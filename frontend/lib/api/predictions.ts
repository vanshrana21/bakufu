import type { MaskMode, PredictionResponse } from "@/lib/contracts";
import { PredictionResponseSchema } from "@/lib/contracts";
import { DEMO_SITES, buildPredictionFixture, type SiteFixture } from "@/fixtures/predictions";
import type { WirePredictPoint } from "./wire";
import { ApiRequestError, LIVE_MODE, apiPost } from "./client";

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

/** The backend returns ONE combined `mask_decision` string, even for
 * `mask=both`, and the frontend contract requires one result per active mask.
 * When the combined decision is an exclusion under `both`, it is not knowable
 * from the response WHICH of the two masks excluded the point — the registry
 * evaluates `in_basement AND in_buffer` and reports the conjunction. Rather than
 * guess an attribution, both entries report the exclusion and say plainly that
 * the backend does not attribute it. The outcome is correct; only the blame is
 * unavailable, and the text says so.
 */
function maskResultsFrom(wire: WirePredictPoint, mask: MaskMode): PredictionResponse["mask_results"] {
  const masks = activeMasks(mask);
  if (masks.length === 0) return [];
  const raw = wire.raw_score;
  const final = wire.final_score;
  const excluded = final === 0 && raw !== null && raw > 0;
  const combined = wire.mask_decision && wire.mask_decision !== "n/a" ? wire.mask_decision.replaceAll("_", " ") : "no decision reported";
  const unattributed = masks.length > 1 && excluded;

  return masks.map((name) => ({
    mask: name,
    outcome: excluded ? ("excluded" as const) : ("passed" as const),
    reason: unattributed
      ? `Excluded under the combined geological ∩ occurrence-buffer policy. The backend reports one decision for both masks ("${combined}") and does not attribute the exclusion to either one individually.`
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
    asset: {
      id: site.id, name: site.name, asset_type: site.asset_type,
      inventory_status: site.synthetic ? ("synthetic" as const) : ("documented" as const),
      assay_status: site.asset_type === "historical_waste_dump" || site.asset_type === "slag_heap"
        ? ("pending" as const) : ("not_applicable" as const),
      occurrence_buffer_membership: site.inside_buffer === null
        ? ("unknown" as const) : site.inside_buffer ? ("inside" as const) : ("outside" as const),
    },
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
      // The backend sends only the top 5 contributions and no base value, so the
      // waterfall cannot be reconciled to the prediction the way the shortfall
      // explanation can. Zero is the neutral origin for the bar chart.
      base_value: 0,
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
      const wire = await apiPost<WirePredictPoint>(
        "/predict/point",
        { lat: site.location.latitude, lon: site.location.longitude, mask },
        { signal },
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
          asset: {
            id: site.id, name: site.name, asset_type: site.asset_type,
            inventory_status: site.synthetic ? "synthetic" : "documented",
            assay_status: site.asset_type === "historical_waste_dump" || site.asset_type === "slag_heap" ? "pending" : "not_applicable",
            occurrence_buffer_membership: site.inside_buffer === null ? "unknown" : site.inside_buffer ? "inside" : "outside",
          },
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
