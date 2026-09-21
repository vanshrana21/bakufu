import { describe, expect, it } from "vitest";
import { ActionResponseSchema, ForecastResponseSchema, PredictionResponseSchema, RiskResponseSchema, type TargetList } from "@/lib/contracts";
import { actionFixture, forecastFixture, riskFixture } from "@/fixtures/operations";
import { createExplorerStore } from "@/stores/explorer-store";
import { ApiRequestError, ContractMismatchError } from "@/lib/api/client";
import { adaptPointPrediction, explainFailure } from "@/lib/api/predictions";
import type { WirePredictPoint } from "@/lib/api/wire";

const HERE = { latitude: 21.5984, longitude: 79.0531 };

/** One /predict/point response as the backend sends it; each test changes
 * only what it is about. */
const wire = (overrides: Partial<WirePredictPoint> = {}): WirePredictPoint => ({
  prospectivity_score: 0.99,
  predicted_type: "gondite",
  uncertainty: 0.08,
  features_extracted: { B04_mean: 0.121, slope_deg: 3.4 },
  shap_top5: [{ feature: "B04_mean", shap_value: 0.81, actual_value: 0.121 }],
  shap_base_value: 0.12,
  model_version: "prospectivity_v6",
  lat: HERE.latitude,
  lon: HERE.longitude,
  prediction_id: 412,
  mask_applied: "both",
  mask_decision: "passed",
  raw_score: 0.99,
  final_score: 0.99,
  raw_probability: 0.997,
  model_margin: 5.85,
  ...overrides,
});

describe("scientific meaning at the API boundary", () => {
  it("gives a point with no imagery no score, and rejects a manufactured one", () => {
    const response = adaptPointPrediction(wire({ features_extracted: { B04_mean: null, slope_deg: null } }), "both", HERE);
    expect(response.scope_status).toBe("unknown");
    expect(response.raw_score).toBeNull();
    expect(response.final_score).toBeNull();
    expect(response.model_margin).toBeNull();
    expect(PredictionResponseSchema.safeParse({ ...response, raw_score: 0.001 }).success).toBe(false);
    expect(PredictionResponseSchema.safeParse({ ...response, model_margin: 2.1 }).success).toBe(false);
  });

  it("preserves the raw score while exposing a mask exclusion, and blames the mask that failed", () => {
    const masked = adaptPointPrediction(wire({ final_score: 0, mask_decision: "masked_out_not_in_buffer" }), "both", HERE);
    expect(masked.raw_score).toBe(0.99);
    expect(masked.final_score).toBe(0);
    expect(masked.mask_results.find((r) => r.mask === "occurrence_buffer")?.outcome).toBe("excluded");
    expect(masked.mask_results.find((r) => r.mask === "geological")?.outcome).toBe("passed");
    expect(PredictionResponseSchema.safeParse({ ...masked, final_score: 0.99 }).success).toBe(false);
  });

  it("requires scores to respect the documented cap and complete mask checks", () => {
    const p = adaptPointPrediction(wire(), "both", HERE);
    expect(p.final_score).toBe(0.99);
    expect(PredictionResponseSchema.safeParse({ ...p, raw_score: 1 }).success).toBe(false);
    expect(PredictionResponseSchema.safeParse({ ...p, mask_results: [] }).success).toBe(false);
    expect(PredictionResponseSchema.safeParse({ ...p, mask_results: [p.mask_results[0], p.mask_results[0]] }).success).toBe(false);
  });

  it("carries the uncapped margin that orders locations the 0.99 cap cannot", () => {
    const p = adaptPointPrediction(wire({ mask_applied: "geological" }), "geological", HERE);
    expect(p.model_margin).toBe(5.85);
    expect(p.raw_probability).toBe(0.997);
    const older = adaptPointPrediction(wire({ mask_applied: "geological", model_margin: undefined, raw_probability: undefined }), "geological", HERE);
    expect(older.model_margin).toBeNull();
  });

  it("refuses a response whose mask is not the one requested", () => {
    expect(() => adaptPointPrediction(wire({ mask_applied: "none" }), "both", HERE)).toThrow(ContractMismatchError);
  });

  it("says what an unauditable score means instead of repeating the raw 503", () => {
    const audit = new ApiRequestError("Prediction computed, but its audit record could not be persisted. Retry the request.", { endpoint: "/predict/point", status: 503 });
    expect(explainFailure(audit)).toMatch(/DATABASE_URL/);
    const other = new ApiRequestError("Model artifact missing", { endpoint: "/predict/point", status: 503 });
    expect(explainFailure(other)).toBe("Model artifact missing");
  });

  it("rejects inverted, one-sided or invented forecast interval metadata", () => {
    const first = forecastFixture.points[0]!;
    expect(ForecastResponseSchema.safeParse({ ...forecastFixture, points: [{ ...first, lower_bound: first.point_estimate + 1 }, ...forecastFixture.points.slice(1)] }).success).toBe(false);
    expect(ForecastResponseSchema.safeParse({ ...forecastFixture, interval: null }).success).toBe(false);
    expect(ForecastResponseSchema.safeParse({ ...forecastFixture, points: [{ ...first, lower_bound: null }, ...forecastFixture.points.slice(1)] }).success).toBe(false);
  });
  it("rejects future observation cutoffs and missing forecast months", () => {
    expect(ForecastResponseSchema.safeParse({ ...forecastFixture, data_cutoff: "2027-01-01T00:00:00Z" }).success).toBe(false);
    expect(ForecastResponseSchema.safeParse({ ...forecastFixture, points: forecastFixture.points.slice(1) }).success).toBe(false);
  });
  it("keeps risk score and probability mutually exclusive", () => {
    expect(RiskResponseSchema.safeParse({ ...riskFixture, probability: 32 }).success).toBe(false);
    expect(RiskResponseSchema.safeParse({ ...riskFixture, score: { value: 32, minimum: 0, maximum: 100, higher_means_more_risk: true } }).success).toBe(false);
    expect(RiskResponseSchema.safeParse({ ...riskFixture, value_type: "score", probability: null, score: { value: 32, minimum: 0, maximum: 100, higher_means_more_risk: true } }).success).toBe(true);
  });
  it("requires review provenance when an action is marked reviewed", () => {
    expect(ActionResponseSchema.safeParse({ ...actionFixture, review_status: "reviewed" }).success).toBe(false);
  });
});

describe("Explorer state", () => {
  const ranking = (ids: string[]): TargetList => ({
    provenance: { data_origin: "live", source: "test", model_version: "prospectivity_v6", generated_at: "2026-09-21T00:00:00Z" },
    bbox: [79.0, 21.3, 80.6, 22.1],
    candidates_considered: 536,
    min_separation_km: 10,
    ranking: "classifier_margin",
    ranking_note: "test",
    targets: ids.map((id, index) => ({
      id, rank: index + 1, label: `${10 + index} km N of Gumgaon`, location: { longitude: 79.05, latitude: 21.6 + index / 100 },
      score: 0.99, neighbourhood_score: 0.9, nearest_mine: "Gumgaon", km_to_nearest_mine: 23, bearing_from_mine: "N",
      precision_m: 323, margin: 5 - index, raw_probability: 0.99,
    })),
  });

  it("does not share stores between users, and keeps a mine and a target apart", () => {
    const a = createExplorerStore(); const b = createExplorerStore();
    a.getState().select({ kind: "mine", id: "Balaghat" });
    a.getState().setMask("none");
    expect(a.getState().selected).toEqual({ kind: "mine", id: "Balaghat" });
    // The ranking runs under the geological mask, so the surface opens on it.
    expect(b.getState().activeMask).toBe("geological");
    expect(b.getState().selected).toBeNull();
    expect(b.getState().targets).toEqual({ status: "loading" });
  });

  it("drops a selected target the new ranking no longer contains, and keeps a mine", () => {
    const store = createExplorerStore();
    store.getState().setTargets({ status: "ready", list: ranking(["T1", "T2"]) });
    store.getState().select({ kind: "target", id: "T2" });
    store.getState().setTargets({ status: "ready", list: ranking(["T1"]) });
    expect(store.getState().selected).toBeNull();
    store.getState().select({ kind: "mine", id: "Ukwa" });
    store.getState().setTargets({ status: "unavailable", reason: "backend down" });
    expect(store.getState().selected).toEqual({ kind: "mine", id: "Ukwa" });
  });
});
