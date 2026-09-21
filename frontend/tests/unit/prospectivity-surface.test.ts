import { describe, expect, it } from "vitest";
import { prospectivityLayers } from "@/lib/map/prospectivity-layers";
import { reviewRegisterFixture, vitalSignsFixture } from "@/fixtures/operations";

describe("Map source and operational fixture consistency", () => {
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
