/** Test style matched from tests/unit/contracts.test.ts: describe/it with
 * safeParse assertions against the schema, and adapter behaviour exercised
 * through the real adapter rather than a mock of it. */

import { describe, expect, it } from "vitest";
import { MineRosterSchema, MineSchema } from "@/lib/contracts";
import { adaptMineRoster } from "@/lib/api/mines";
import { groupOf } from "@/components/mines/fleet-summary";
import type { WireMine, WireMines, WirePredictPoint } from "@/lib/api/wire";

const wireMine = (overrides: Partial<WireMine> = {}): WireMine => ({
  mine_name: "Balaghat",
  state: "MP",
  district: "Balaghat",
  mine_type: "underground",
  equipment: ["SDL"],
  capacity_target_tonnes: 800000,
  notes: "Deepest underground manganese mine in Asia.",
  sources: [{ tag: "IBM_2022", url: "https://ibm.gov.in/example.pdf" }],
  type_note: null,
  lat: 21.8333,
  lon: 80.2333,
  confidence: "high",
  source: "MoEFCC PFR boundary centroid",
  source_url: null,
  coordinate_precision: null,
  coordinate_note: null,
  ...overrides,
});

const wireRoster = (mines: WireMine[]): WireMines => ({
  mines,
  counts: {
    total: mines.length,
    underground: mines.filter((m) => m.mine_type === "underground").length,
    opencast: mines.filter((m) => m.mine_type === "opencast").length,
    mixed: 0, MH: 0, MP: 0, with_capacity_target: 0, with_generic_fleet_only: 0,
  },
});

const wireScore = (value: number): WirePredictPoint => ({
  prospectivity_score: value,
  predicted_type: "unknown",
  uncertainty: 0.5,
  features_extracted: { b02: 746 },
  shap_top5: [
    { feature: "elevation", shap_value: 0.671, actual_value: 302.1 },
    { feature: "slope", shap_value: -0.882, actual_value: 0.101 },
  ],
  model_version: "prospectivity_v6",
  lat: 21.8333,
  lon: 80.2333,
  prediction_id: 1,
  mask_applied: "none",
  mask_decision: "n/a",
  raw_score: value,
  final_score: value,
});

describe("mine roster at the API boundary", () => {
  it("maps a scored mine onto the roster contract", () => {
    const roster = adaptMineRoster(wireRoster([wireMine()]), [
      { score: wireScore(0.3352), error: null },
    ]);
    expect(MineRosterSchema.safeParse(roster).success).toBe(true);
    const mine = roster.mines[0]!;
    expect(mine.name).toBe("Balaghat");
    expect(mine.score?.value).toBe(0.3352);
    expect(mine.score_error).toBeNull();
    // Feature names are humanised for display, never renamed in the data.
    expect(mine.score?.drivers.map((d) => d.feature)).toEqual(["elevation", "slope"]);
    expect(mine.score?.drivers[1]!.label).toBe("slope");
  });

  it("keeps a nullable source_url and coordinate_precision", () => {
    const roster = adaptMineRoster(
      wireRoster([
        wireMine({ source_url: null, coordinate_precision: null }),
        wireMine({
          mine_name: "Dongri Buzurg",
          mine_type: "opencast",
          source_url: "https://en.wikipedia.org/wiki/Dongri_Buzurg_railway_station",
          coordinate_precision: "approximate — 1-2 km from the mine boundary",
        }),
      ]),
      [
        { score: wireScore(0.3352), error: null },
        { score: wireScore(0.3271), error: null },
      ],
    );
    expect(MineRosterSchema.safeParse(roster).success).toBe(true);
    expect(roster.mines[0]!.coordinate_source_url).toBeNull();
    expect(roster.mines[0]!.coordinate_precision).toBeNull();
    expect(roster.mines[1]!.coordinate_precision).toContain("approximate");
  });

  it("carries a no-imagery failure as a stated reason, not a zero", () => {
    const roster = adaptMineRoster(wireRoster([wireMine({ mine_name: "Gumgaon" })]), [
      { score: null, error: "Sentinel-2 mosaic does not cover (21.4, 78.9)" },
    ]);
    const mine = roster.mines[0]!;
    expect(mine.score).toBeNull();
    expect(mine.score_error).toContain("does not cover");
    // A score of zero would read as "no manganese" rather than "no data".
    expect(MineSchema.safeParse({ ...mine, score_error: null }).success).toBe(false);
  });

  it("rejects a mine carrying both a score and an error", () => {
    const roster = adaptMineRoster(wireRoster([wireMine()]), [
      { score: wireScore(0.5), error: null },
    ]);
    const mine = roster.mines[0]!;
    expect(MineSchema.safeParse({ ...mine, score_error: "stale failure" }).success).toBe(false);
  });

  it("rejects a score above the documented cap and a count that disagrees", () => {
    const roster = adaptMineRoster(wireRoster([wireMine()]), [
      { score: wireScore(0.99), error: null },
    ]);
    expect(MineRosterSchema.safeParse(roster).success).toBe(true);
    const overCap = { ...roster, mines: [{ ...roster.mines[0]!, score: { ...roster.mines[0]!.score!, value: 1 } }] };
    expect(MineRosterSchema.safeParse(overCap).success).toBe(false);
    expect(MineRosterSchema.safeParse({ ...roster, counts: { ...roster.counts, total: 9 } }).success).toBe(false);
  });

  it("bands mines by the documented score floors", () => {
    const mine = (value: number | null) =>
      adaptMineRoster(wireRoster([wireMine()]), [
        value === null
          ? { score: null, error: "no imagery" }
          : { score: wireScore(value), error: null },
      ]).mines[0]!;
    expect(groupOf(mine(0.97))).toBe("recognised");
    expect(groupOf(mine(0.85))).toBe("recognised");
    expect(groupOf(mine(0.68))).toBe("mixed");
    expect(groupOf(mine(0.35))).toBe("mixed");
    expect(groupOf(mine(0.3352))).toBe("low");
    expect(groupOf(mine(null))).toBeNull();
  });

  it("attaches the measured caveat to the mines that need one", () => {
    const roster = adaptMineRoster(
      wireRoster([wireMine(), wireMine({ mine_name: "Ukwa" })]),
      [
        { score: wireScore(0.3352), error: null },
        { score: wireScore(0.99), error: null },
      ],
    );
    expect(roster.mines[0]!.caveat).toContain("±2 km");
    // A caveat is stated where it is measured, not attached to every card.
    expect(roster.mines[1]!.caveat).toBeNull();
  });
});
