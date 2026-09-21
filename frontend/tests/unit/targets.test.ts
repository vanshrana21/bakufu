import { describe, expect, it } from "vitest";
import type { MineLocation } from "@/lib/contracts";
import type { WireHeatmap } from "@/lib/api/wire";
import { MIN_SEPARATION_KM, bearingFrom, cellsOf, haversineKm, shortlist } from "@/lib/api/targets";

/** A square lattice over a real-sized bbox, row-major from the top-left. */
function lattice(scores: (number | null)[][], bbox: [number, number, number, number] = [79.0, 21.3, 80.6, 22.1]): WireHeatmap {
  const rows = scores.length;
  const cols = scores[0]!.length;
  return {
    bbox,
    grid: { n_cols: cols, n_rows: rows, cell_width_deg: (bbox[2] - bbox[0]) / cols, cell_height_deg: (bbox[3] - bbox[1]) / rows, origin: "top_left" },
    scores,
    cells: { cells_total: rows * cols, cells_outside_raster: 0, cells_masked_out: 0, cells_scored: rows * cols },
    score_range: { min: 0, max: 0.99, cap: 0.99 },
    mask_applied: "geological",
    model_version: "prospectivity_v6",
    generated_at: "2026-09-21T00:00:00Z",
    cached: true,
  } as WireHeatmap;
}

const MINES: MineLocation[] = [
  { name: "West mine", mine_type: "underground", location: { longitude: 79.1, latitude: 21.7 } },
  { name: "East mine", mine_type: "opencast", location: { longitude: 80.5, latitude: 21.7 } },
];

describe("geometry helpers", () => {
  it("measures a degree of latitude as about 111 km", () => {
    expect(haversineKm(21, 80, 22, 80)).toBeCloseTo(111.2, 0);
  });

  it("names the compass direction from the first point to the second", () => {
    expect(bearingFrom(21.5, 80, 21.9, 80)).toBe("N");
    expect(bearingFrom(21.5, 80, 21.5, 80.4)).toBe("E");
    expect(bearingFrom(21.5, 80, 21.2, 79.7)).toBe("SW");
  });

  it("places cell centres from the top-left corner, latitude falling with the row", () => {
    const cells = cellsOf(lattice([[0.1, 0.2], [0.3, 0.4]], [79, 21, 80, 22]));
    expect(cells[0]).toMatchObject({ row: 0, col: 0, lat: 21.75, lon: 79.25, score: 0.1 });
    expect(cells[3]).toMatchObject({ row: 1, col: 1, lat: 21.25, lon: 79.75, score: 0.4 });
  });
});

describe("greenfield shortlist", () => {
  // 6 x 6 over the belt. Three hot interior cells: (1,1) and (4,4) are far
  // apart; (1,2) sits next to (1,1). (2,3) is hot but inside a known buffer.
  const basement = lattice([
    [0.99, 0.99, 0.99, 0.99, 0.99, 0.99],
    [0.2, 0.99, 0.98, 0.1, 0.1, 0.2],
    [0.2, 0.9, 0.1, 0.99, 0.1, 0.2],
    [0.1, 0.1, 0.1, 0.1, 0.1, 0.1],
    [0.1, 0.1, 0.1, 0.1, 0.99, 0.1],
    [0.1, 0.1, 0.1, 0.1, 0.1, 0.1],
  ]);
  // Occurrence-buffer mask: > 0 means the cell lies inside a known 5 km buffer.
  const buffered = lattice([
    [0, 0, 0, 0, 0, 0],
    [0, 0, 0, 0, 0, 0],
    [0, 0, 0, 0.99, 0, 0],
    [0, 0, 0, 0, 0, 0],
    [0, 0, 0, 0, 0, 0],
    [0, 0, 0, 0, 0, 0],
  ]);

  const { candidates, chosen } = shortlist(basement, buffered, MINES);

  it("drops the perimeter ring, where the imagery edge makes features least reliable", () => {
    expect(candidates.every((cell) => cell.row > 0 && cell.col > 0 && cell.row < 5 && cell.col < 5)).toBe(true);
  });

  it("drops ground inside a known occurrence buffer: that is not a new find", () => {
    expect(candidates.some((cell) => cell.row === 2 && cell.col === 3)).toBe(false);
  });

  it("orders by score first, then by how coherent the neighbourhood is", () => {
    expect(candidates[0]).toMatchObject({ row: 1, col: 1 });
    // (1,1) has hot neighbours on three sides; (4,4) sits alone in cold ground.
    const lone = candidates.find((cell) => cell.row === 4 && cell.col === 4)!;
    expect(candidates[0]!.neighbourhood).toBeGreaterThan(lone.neighbourhood);
  });

  it("keeps every chosen target at least the minimum separation apart", () => {
    for (const a of chosen) {
      for (const b of chosen) {
        if (a !== b) expect(haversineKm(a.lat, a.lon, b.lat, b.lon)).toBeGreaterThanOrEqual(MIN_SEPARATION_KM);
      }
    }
  });

  it("names the nearest known mine for each candidate", () => {
    expect(candidates.find((cell) => cell.row === 1 && cell.col === 1)!.nearest.name).toBe("West mine");
    expect(candidates.find((cell) => cell.row === 4 && cell.col === 4)!.nearest.name).toBe("East mine");
  });

  it("returns nothing, rather than inventing a frame of reference, when no mines are known", () => {
    expect(shortlist(basement, buffered, [])).toEqual({ candidates: [], chosen: [] });
  });
});
