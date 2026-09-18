import { describe, expect, it } from "vitest";
import { buildProspectivitySurface } from "@/fixtures/prospectivity-surface";
import { DEMO_SITES, isGhostReserveCandidate } from "@/fixtures/predictions";
import { prospectivityLayers } from "@/lib/map/prospectivity-layers";
import { reviewRegisterFixture, vitalSignsFixture } from "@/fixtures/operations";

describe("Map source and operational fixture consistency", () => {
  it("preserves the diagnostic raw score while hatching its policy-zero surface", () => {
    const screened = buildProspectivitySurface(DEMO_SITES, "both");
    const diagnostic = screened.features.find((f) => f.properties.site_id === "farmland-control")!;
    expect(diagnostic.properties).toMatchObject({ raw_score: .99, final_score: 0, mask_excluded: true, mask_applied: "both" });
    const raw = buildProspectivitySurface(DEMO_SITES, "none").features.find((f) => f.properties.site_id === "farmland-control")!;
    expect(raw.properties).toMatchObject({ raw_score: .99, final_score: .99, mask_excluded: false });
    expect(screened.features.every((f) => f.properties.scope_status === "in_scope")).toBe(true);
    expect(screened.features).toHaveLength(4); // Sandur/Bonai never become zero-score cells.
  });
  it("keeps exactly two eligible Ghost assets with every mask disabled", () => {
    const cells = buildProspectivitySurface(DEMO_SITES.filter(isGhostReserveCandidate), "none");
    expect(cells.features.map((f) => f.properties.site_id)).toEqual(["demo-dump-a", "demo-slag-b"]);
  });
  it("adapts the same committed layer spec to GeoJSON without corrupting vector mode", () => {
    expect(prospectivityLayers("geojson").every((l) => !("source-layer" in l))).toBe(true);
    expect(prospectivityLayers("vector").every((l) => l["source-layer"] === "prediction_cells")).toBe(true);
    expect(prospectivityLayers("geojson").find((l) => l.id === "prospectivity-excluded")?.paint?.["fill-pattern"]).toBe("excluded-hatch");
  });
  it("counts proposed reviews from the same register that users inspect", () => {
    expect(reviewRegisterFixture).toHaveLength(4);
    expect(vitalSignsFixture.pending_reviews).toBe(reviewRegisterFixture.filter(({ action }) => action.review_status === "proposed").length);
    expect(new Set(reviewRegisterFixture.map(({ action }) => action.action_id)).size).toBe(4);
  });
});
