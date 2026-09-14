import { describe, expect, it } from "vitest";
import { ActionResponseSchema, ForecastResponseSchema, PredictionResponseSchema, RiskResponseSchema } from "@/lib/contracts";
import { buildPredictionFixture, DEMO_SITES, isGhostReserveCandidate } from "@/fixtures/predictions";
import { actionFixture, forecastFixture, riskFixture } from "@/fixtures/operations";
import { createExplorerStore } from "@/stores/explorer-store";
import { predictionClient } from "@/lib/api/predictions";

describe("scientific meaning at the API boundary", () => {
  it.each(["sandur", "bonai"])("%s has no score, and rejects a manufactured low score", (id) => {
    const response = buildPredictionFixture(id, "both");
    expect(response.scope_status).toBe("out_of_scope");
    expect(response.raw_score).toBeNull();
    expect(response.final_score).toBeNull();
    expect(PredictionResponseSchema.safeParse({ ...response, raw_score: 0.001 }).success).toBe(false);
  });
  it("preserves a false-positive raw score while exposing a mask exclusion", () => {
    expect(buildPredictionFixture("farmland-control", "none").final_score).toBe(0.99);
    const masked = buildPredictionFixture("farmland-control", "both");
    expect(masked.raw_score).toBe(0.99);
    expect(masked.final_score).toBe(0);
    expect(masked.mask_results.find((r) => r.mask === "occurrence_buffer")?.outcome).toBe("excluded");
    expect(PredictionResponseSchema.safeParse({ ...masked, final_score: 0.99 }).success).toBe(false);
  });
  it("requires scores to respect the documented cap and complete mask checks", () => {
    const p = buildPredictionFixture("demo-dump-a", "both");
    expect(PredictionResponseSchema.safeParse({ ...p, raw_score: 1 }).success).toBe(false);
    expect(PredictionResponseSchema.safeParse({ ...p, mask_results: [] }).success).toBe(false);
    expect(PredictionResponseSchema.safeParse({ ...p, mask_results: [p.mask_results[0], p.mask_results[0]] }).success).toBe(false);
  });
  it("does not include outside/unknown buffer membership in Ghost mode", () => {
    expect(DEMO_SITES.filter(isGhostReserveCandidate).map((s) => s.id)).toEqual(["demo-dump-a", "demo-slag-b"]);
    const source = DEMO_SITES[0]!;
    expect(isGhostReserveCandidate({ ...source, inside_buffer: null })).toBe(false);
    expect(isGhostReserveCandidate({ ...source, scope_status: "unknown" })).toBe(false);
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
describe("state isolation and cancellation", () => {
  it("does not share stores between users and keeps Ghost filtering independent of masks", () => {
    const a = createExplorerStore(); const b = createExplorerStore();
    a.getState().selectSite("demo-dump-c");
    a.getState().setGhostOnly(true);
    a.getState().setMask("none");
    expect(a.getState().selectedSiteId).toBeNull();
    expect(a.getState().ghostOnly).toBe(true);
    expect(b.getState().activeMask).toBe("both");
    expect(b.getState().ghostOnly).toBe(false);
  });
  it("cancels a superseded mock request", async () => {
    const controller = new AbortController();
    const pending = predictionClient.predict("demo-dump-a", "both", controller.signal);
    controller.abort();
    await expect(pending).rejects.toMatchObject({ name: "AbortError" });
  });
});
