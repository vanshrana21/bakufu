/** Test style matched from tests/unit/contracts.test.ts and mines.test.ts:
 * describe/it, schema assertions, and the real adapter exercised against a
 * stubbed backend rather than a mock of the adapter itself.
 *
 * The API base URL is stubbed before importing, because lib/api/client.ts
 * reads it once at module scope to decide live mode.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { TargetListSchema } from "@/lib/contracts";

const BBOX = [79.0, 21.3, 80.6, 22.1] as const;
/** The grid the adapter asks for. Pinned by a test below, because a stub built
 * for a different size silently falls through to the refinement branch and the
 * ranking then runs on nonsense. */
const GRID = 32;
const REFINE = 8;

/** Cells of interest, chosen far enough apart to clear the separation rule.
 * A 32x32 cell over this bbox is ~5.2 x 2.8 km, so neighbours are closer than
 * the 10 km minimum and only one of a cluster can be chosen. */
const COHERENT: [number, number] = [5, 5];   // caps, neighbours also high
const ISOLATED: [number, number] = [5, 20];  // caps, neighbours cold
const KNOWN: [number, number] = [20, 5];     // caps, but inside the buffer

const MINES = {
  mines: [{
    mine_name: "Tirodi", state: "MP", district: "Balaghat", mine_type: "underground",
    equipment: [], capacity_target_tonnes: null, notes: "", sources: [], type_note: null,
    lat: 21.35, lon: 79.05, confidence: "high", source: "test", source_url: null,
    coordinate_precision: null, coordinate_note: null,
  }],
  counts: { total: 1, underground: 1, opencast: 0, mixed: 0, MH: 0, MP: 1, with_capacity_target: 0, with_generic_fleet_only: 0 },
};

function beltScores(mask: string): number[][] {
  const scores: number[][] = Array.from({ length: GRID }, () => Array(GRID).fill(0.2));
  if (mask === "occurrence_buffer") {
    // Only the known cell survives this mask; a zero here is what marks every
    // other cell as greenfield.
    const masked: number[][] = Array.from({ length: GRID }, () => Array(GRID).fill(0));
    masked[KNOWN[0]]![KNOWN[1]] = 0.99;
    return masked;
  }
  scores[0]![0] = 0.99;                                   // perimeter: ignored
  scores[COHERENT[0]]![COHERENT[1]] = 0.99;
  for (const [dr, dc] of [[-1, 0], [1, 0], [0, -1], [0, 1]]) {
    scores[COHERENT[0] + dr!]![COHERENT[1] + dc!] = 0.9;  // coherent surround
  }
  scores[ISOLATED[0]]![ISOLATED[1]] = 0.99;
  for (const [dr, dc] of [[-1, 0], [1, 0], [0, -1], [0, 1]]) {
    scores[ISOLATED[0] + dr!]![ISOLATED[1] + dc!] = 0.05; // cold surround
  }
  scores[KNOWN[0]]![KNOWN[1]] = 0.99;
  return scores;
}

function payload(scores: number[][], bbox: number[], grid: number, mask: string) {
  return {
    bbox,
    grid: {
      n_cols: grid, n_rows: grid,
      cell_width_deg: (bbox[2]! - bbox[0]!) / grid,
      cell_height_deg: (bbox[3]! - bbox[1]!) / grid,
      origin: "top_left",
    },
    scores,
    cells: { cells_total: grid * grid, cells_outside_raster: 0, cells_masked_out: 0, cells_scored: grid * grid },
    score_range: { min: 0, max: 0.99, cap: 0.99 },
    mask_applied: mask,
    model_version: "prospectivity_v6",
    generated_at: "2026-09-17T00:00:00Z",
    cached: true,
  };
}

let refineCalls: string[] = [];
let pointCalls: Array<{ lat: number; lon: number }> = [];

/** Margins are a function of latitude, so the expected order is knowable here
 * and deliberately differs from the shortlist order. */
const marginFor = (lat: number) => (lat - 21) * 10;

function stubFetch() {
  return vi.fn(async (input: string | URL, init?: RequestInit) => {
    const url = new URL(String(input));
    if (url.pathname === "/mines") return new Response(JSON.stringify(MINES), { status: 200 });

    if (url.pathname === "/predict/point") {
      const body = JSON.parse(String(init?.body ?? "{}")) as { lat: number; lon: number };
      pointCalls.push(body);
      const margin = marginFor(body.lat);
      return new Response(
        JSON.stringify({
          prospectivity_score: 0.99, predicted_type: "unknown", uncertainty: 0.02,
          features_extracted: {}, shap_top5: [], model_version: "prospectivity_v6",
          lat: body.lat, lon: body.lon, prediction_id: 1,
          mask_applied: "none", mask_decision: "n/a", raw_score: 0.99, final_score: 0.99,
          model_margin: margin, raw_probability: 1 / (1 + Math.exp(-margin)),
        }),
        { status: 200 },
      );
    }

    const grid = Number(url.searchParams.get("grid_size"));
    const mask = url.searchParams.get("mask") ?? "none";
    const bbox = [
      Number(url.searchParams.get("min_lon")), Number(url.searchParams.get("min_lat")),
      Number(url.searchParams.get("max_lon")), Number(url.searchParams.get("max_lat")),
    ];
    if (grid === GRID) return new Response(JSON.stringify(payload(beltScores(mask), bbox, GRID, mask)), { status: 200 });

    // Refinement pass: the best sub-cell sits in the corner, so the returned
    // coordinate must move off the parent cell's centre.
    refineCalls.push(url.search);
    const local: number[][] = Array.from({ length: grid }, () => Array(grid).fill(0.4));
    local[0]![0] = 0.99;
    return new Response(JSON.stringify(payload(local, bbox, grid, mask)), { status: 200 });
  });
}

describe("top greenfield targets", () => {
  beforeEach(() => {
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://backend.test");
    vi.stubGlobal("fetch", stubFetch());
    refineCalls = [];
    pointCalls = [];
    vi.resetModules();
  });
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  const load = () => import("@/lib/api/targets");
  const run = async () => (await load()).fetchTopTargets();

  it("asks for the grid this stub is built for", async () => {
    const { TARGET_GRID, REFINE_GRID, TARGET_BBOX } = await load();
    expect(TARGET_GRID).toBe(GRID);
    expect(REFINE_GRID).toBe(REFINE);
    expect(TARGET_BBOX).toEqual([...BBOX]);
  });

  it("returns a schema-valid list ranked consecutively from 1", async () => {
    const list = await run();
    expect(TargetListSchema.safeParse(list).success).toBe(true);
    expect(list.targets.length).toBeGreaterThan(1);
    expect(list.targets.map((t) => t.rank)).toEqual(
      Array.from({ length: list.targets.length }, (_, i) => i + 1),
    );
    expect(list.targets[0]!.id).toBe("T1");
  });

  it("shortlists a coherent anomaly ahead of an isolated cap cell", async () => {
    const list = await run();
    // Shortlisting, not final order: the margin orders the ten, but coherence
    // decides which cells get one of the slots. Both cap cells qualify, so each
    // is found here by its surroundings rather than by its position.
    const coherent = list.targets.find((t) => t.neighbourhood_score > 0.3);
    const isolated = list.targets.find((t) => t.neighbourhood_score < 0.2);
    expect(coherent).toBeDefined();
    expect(isolated).toBeDefined();
    expect(coherent!.score).toBeCloseTo(0.99);
    expect(isolated!.score).toBeCloseTo(0.99);
    expect(coherent!.neighbourhood_score).toBeGreaterThan(isolated!.neighbourhood_score);
  });

  it("excludes ground inside the occurrence buffer", async () => {
    const list = await run();
    expect(list.targets.every((t) => t.greenfield)).toBe(true);
    const height = (BBOX[3] - BBOX[1]) / GRID;
    const width = (BBOX[2] - BBOX[0]) / GRID;
    const knownLat = BBOX[3] - (KNOWN[0] + 0.5) * height;
    const knownLon = BBOX[0] + (KNOWN[1] + 0.5) * width;
    // The refined coordinate moves within its own cell, so a half-cell box
    // around the known centre is the right test.
    const hit = list.targets.some(
      (t) => Math.abs(t.location.latitude - knownLat) < height / 2
        && Math.abs(t.location.longitude - knownLon) < width / 2,
    );
    expect(hit).toBe(false);
  });

  it("refines every chosen target and reports the precision achieved", async () => {
    const list = await run();
    expect(refineCalls).toHaveLength(list.targets.length);
    for (const call of refineCalls) expect(call).toContain(`grid_size=${REFINE}`);
    for (const target of list.targets) {
      expect(target.precision_m).toBeGreaterThan(0);
      expect(target.precision_m).toBeLessThan(1000);
    }
  });

  it("orders the shortlist by the classifier margin, not the capped score", async () => {
    const list = await run();
    // Every target reports the same capped score, so the score cannot order them.
    expect(new Set(list.targets.map((t) => t.score))).toEqual(new Set([0.99]));
    const margins = list.targets.map((t) => t.margin as number);
    expect(margins.every((m) => typeof m === "number")).toBe(true);
    expect([...margins]).toEqual([...margins].sort((a, b) => b - a));
    // Ranks and ids are renumbered to the final order, not the shortlist order.
    expect(list.targets.map((t) => t.id)).toEqual(
      list.targets.map((_, index) => `T${index + 1}`),
    );
    expect(pointCalls).toHaveLength(list.targets.length);
  });

  it("carries the uncapped probability beside the capped score", async () => {
    const list = await run();
    for (const target of list.targets) {
      expect(target.raw_probability).not.toBeNull();
      expect(target.raw_probability as number).toBeGreaterThan(0);
      expect(target.raw_probability as number).toBeLessThanOrEqual(1);
    }
  });

  it("keeps the shortlist order when a backend sends no margin", async () => {
    // Contract v1.9 and older: the fields are absent, so nothing can be
    // reordered and the list must not pretend otherwise.
    vi.stubGlobal("fetch", vi.fn(async (input: string | URL, init?: RequestInit) => {
      const url = new URL(String(input));
      if (url.pathname === "/predict/point") {
        const body = JSON.parse(String(init?.body ?? "{}")) as { lat: number; lon: number };
        return new Response(JSON.stringify({
          prospectivity_score: 0.99, predicted_type: "unknown", uncertainty: 0.02,
          features_extracted: {}, shap_top5: [], model_version: "prospectivity_v6",
          lat: body.lat, lon: body.lon, prediction_id: 1,
          mask_applied: "none", mask_decision: "n/a", raw_score: 0.99, final_score: 0.99,
        }), { status: 200 });
      }
      return stubFetch()(input, init);
    }));
    const list = await run();
    expect(list.targets.every((t) => t.margin === null)).toBe(true);
    expect(list.targets[0]!.neighbourhood_score).toBeGreaterThanOrEqual(
      list.targets[1]!.neighbourhood_score,
    );
  });

  it("names each target by bearing and distance from the nearest mine", async () => {
    const list = await run();
    for (const target of list.targets) {
      expect(target.nearest_mine).toBe("Tirodi");
      expect(target.label).toMatch(/^\d+ km (N|NE|E|SE|S|SW|W|NW) of Tirodi$/);
      expect(target.km_to_nearest_mine).toBeGreaterThan(0);
    }
  });

  it("keeps targets at least the stated distance apart", async () => {
    const { haversineKm } = await load();
    const list = await run();
    for (const a of list.targets) {
      for (const b of list.targets) {
        if (a.id === b.id) continue;
        expect(
          haversineKm(a.location.latitude, a.location.longitude, b.location.latitude, b.location.longitude),
        ).toBeGreaterThanOrEqual(list.min_separation_km);
      }
    }
  });
});
