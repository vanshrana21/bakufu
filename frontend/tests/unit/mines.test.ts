import { describe, expect, it } from "vitest";
import { MineSchema } from "@/lib/contracts";
import { MINES_REFERENCE, MINES_REFERENCE_DATE } from "@/fixtures/mines";
import { MINE_CAVEATS, adaptMine, fixtureRoster, mineLocations } from "@/lib/api/mines";
import type { WirePredictPoint } from "@/lib/api/wire";

const balaghat = MINES_REFERENCE.find((mine) => mine.mine_name === "Balaghat")!;

const point = (overrides: Partial<WirePredictPoint> = {}): WirePredictPoint => ({
  prospectivity_score: 0.99,
  predicted_type: "sausar_gondite",
  uncertainty: 0.02,
  features_extracted: {},
  shap_top5: [
    { feature: "elevation", shap_value: 1.27, actual_value: 540 },
    { feature: "ae_12", shap_value: -0.4, actual_value: null },
  ],
  shap_base_value: -1.2,
  model_version: "prospectivity_v6",
  lat: balaghat.lat,
  lon: balaghat.lon,
  prediction_id: 7,
  mask_applied: "none",
  mask_decision: "n/a",
  raw_score: 0.9900000095367432,
  final_score: 0.9900000095367432,
  raw_probability: 0.997,
  model_margin: 5.85,
  ...overrides,
});

describe("mine roster adapter", () => {
  it("reads the reference snapshot: ten mines, seven underground, three opencast", () => {
    const roster = fixtureRoster(MINES_REFERENCE, MINES_REFERENCE_DATE);
    expect(roster.counts).toEqual({ total: 10, underground: 7, opencast: 3, maharashtra: 6, madhya_pradesh: 4 });
    expect(roster.provenance.data_origin).toBe("fixture");
  });

  it("never invents a score in a build without a backend", () => {
    const roster = fixtureRoster(MINES_REFERENCE, MINES_REFERENCE_DATE);
    for (const mine of roster.mines) {
      expect(mine.score).toBeNull();
      expect(mine.score_unavailable).toMatch(/live model/);
    }
  });

  it("clips float32 noise above the 0.99 cap and keeps the classifier's own margin", () => {
    const mine = adaptMine(balaghat, { score: point(), error: null });
    expect(mine.score?.value).toBe(0.99);
    expect(mine.score?.margin).toBe(5.85);
    expect(mine.score?.drivers[0]).toEqual({ label: "elevation", contribution: 1.27, value: 540 });
  });

  it("spells out the state and carries the measured caveat", () => {
    const mine = adaptMine(balaghat, { score: point(), error: null });
    expect(mine.state).toBe("Madhya Pradesh");
    expect(mine.caveat).toBe(MINE_CAVEATS.Balaghat);
  });

  it("turns a failed point query into a stated reason, never a zero", () => {
    const mine = adaptMine(balaghat, { score: null, error: "Prediction computed, but its audit record could not be persisted." });
    expect(mine.score).toBeNull();
    expect(mine.score_unavailable).toMatch(/audit record/);
  });

  it("refuses a card that has neither a score nor a reason", () => {
    const blank = { ...adaptMine(balaghat, { score: point(), error: null }), score: null, score_unavailable: null };
    expect(MineSchema.safeParse(blank).success).toBe(false);
  });

  it("hands the Explorer only where each mine is", () => {
    const locations = mineLocations(MINES_REFERENCE);
    expect(locations).toHaveLength(10);
    expect(locations[0]).toEqual({ name: "Balaghat", mine_type: "underground", location: { longitude: balaghat.lon, latitude: balaghat.lat } });
  });
});
