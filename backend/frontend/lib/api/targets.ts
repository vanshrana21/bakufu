/** Top greenfield exploration targets, derived from the served heatmap.
 *
 * Adapter pattern matched from lib/api/heatmap.ts and lib/api/mines.ts: the
 * backend shapes stay in wire.ts, the contract the UI renders lives in
 * lib/contracts.ts, and nothing is invented here.
 *
 * There is no "top targets" endpoint. This composes three existing ones:
 *
 *   1. GET /mines                                  the ten known mines
 *   2. GET /prospectivity/heatmap mask=geological  candidate ground, basement only
 *   3. GET /prospectivity/heatmap mask=occurrence_buffer
 *                                                  which cells are already known
 *
 * then refines each winner with a small local heatmap over its own cell.
 *
 * Why the ranking is not simply "highest score": 193 of 1,024 cells sit at the
 * 0.99 cap, so score alone leaves a 193-way tie and the order would come from
 * array position. Two measured criteria break it:
 *
 *   - greenfield only. A cell inside the 5 km occurrence buffer is ground
 *     somebody already found; it cannot be a new prediction.
 *   - neighbourhood coherence. A cap-scoring cell whose eight neighbours also
 *     score high is a coherent anomaly; a lone hot pixel beside cold ground is
 *     more likely noise. Ranking by distance-from-mine was tried first and
 *     rejected: that measure maximises at the corners of the bbox, so it
 *     selected the edge of the study area rather than geology.
 *
 * Those two SHORTLIST. The order of the ten comes from the classifier's own
 * margin at each refined coordinate, read from /predict/point: the served
 * score is capped at 0.99 and every target sits on it, while the margins
 * measured 2.27 to 5.85 across the same ten.
 */

import type { MaskMode, TargetList } from "@/lib/contracts";
import { TargetListSchema } from "@/lib/contracts";
import type { WireHeatmap, WireMines, WirePredictPoint } from "./wire";
import { HEATMAP_TIMEOUT_MS, PREDICT_POINT_TIMEOUT_MS, apiGet, apiPost } from "./client";

/** The pre-warmed belt viewport. Requesting one the backend did not warm is
 * what makes the map look hung: a cold heatmap is ~38s. */
export const TARGET_BBOX: [number, number, number, number] = [79.0, 21.3, 80.6, 22.1];
export const TARGET_GRID = 32;
/** 8 is the backend minimum, and over one cell it lands at ~350 m. */
export const REFINE_GRID = 8;
/** Without this, ten cells of one anomaly fill the list. */
export const MIN_SEPARATION_KM = 10;
export const TOP_N = 10;

const COMPASS = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"] as const;

export function haversineKm(lat1: number, lon1: number, lat2: number, lon2: number): number {
  const radius = 6371.0088;
  const p1 = (lat1 * Math.PI) / 180;
  const p2 = (lat2 * Math.PI) / 180;
  const dp = p2 - p1;
  const dl = ((lon2 - lon1) * Math.PI) / 180;
  const a = Math.sin(dp / 2) ** 2 + Math.cos(p1) * Math.cos(p2) * Math.sin(dl / 2) ** 2;
  return 2 * radius * Math.asin(Math.sqrt(a));
}

export function bearingFrom(lat1: number, lon1: number, lat2: number, lon2: number) {
  const p1 = (lat1 * Math.PI) / 180;
  const p2 = (lat2 * Math.PI) / 180;
  const dl = ((lon2 - lon1) * Math.PI) / 180;
  const y = Math.sin(dl) * Math.cos(p2);
  const x = Math.cos(p1) * Math.sin(p2) - Math.sin(p1) * Math.cos(p2) * Math.cos(dl);
  const degrees = ((Math.atan2(y, x) * 180) / Math.PI + 360) % 360;
  return COMPASS[Math.floor((degrees + 22.5) / 45) % 8]!;
}

interface Cell { row: number; col: number; lat: number; lon: number; score: number | null }

/** Cell centres in WGS84. The lattice is row-major from the top-left corner. */
export function cellsOf(wire: WireHeatmap): Cell[] {
  const [minLon, , , maxLat] = wire.bbox;
  const { cell_width_deg: width, cell_height_deg: height } = wire.grid;
  return wire.scores.flatMap((values, row) =>
    values.map((score, col) => ({
      row, col,
      lat: maxLat - (row + 0.5) * height,
      lon: minLon + (col + 0.5) * width,
      score,
    })),
  );
}

const heatmap = (
  bbox: [number, number, number, number],
  gridSize: number,
  mask: MaskMode,
  signal?: AbortSignal,
) =>
  apiGet<WireHeatmap>("/prospectivity/heatmap", {
    query: {
      min_lon: bbox[0], min_lat: bbox[1], max_lon: bbox[2], max_lat: bbox[3],
      grid_size: gridSize, mask,
    },
    timeoutMs: HEATMAP_TIMEOUT_MS,
    signal,
  });

export async function fetchTopTargets(signal?: AbortSignal): Promise<TargetList> {
  const [mines, basement, buffered] = await Promise.all([
    apiGet<WireMines>("/mines", { signal }),
    heatmap(TARGET_BBOX, TARGET_GRID, "geological", signal),
    heatmap(TARGET_BBOX, TARGET_GRID, "occurrence_buffer", signal),
  ]);

  // A cell zeroed under the occurrence-buffer mask, while scoring under the
  // geological one, lies outside the 5 km buffer: ground nobody has logged.
  const known = new Map<string, boolean>();
  for (const cell of cellsOf(buffered)) known.set(`${cell.row}:${cell.col}`, (cell.score ?? 0) > 0);

  const cells = cellsOf(basement);
  const scoreAt = new Map<string, number | null>();
  for (const cell of cells) scoreAt.set(`${cell.row}:${cell.col}`, cell.score);

  const neighbourhoodOf = (row: number, col: number) => {
    const values: number[] = [];
    for (const dr of [-1, 0, 1]) {
      for (const dc of [-1, 0, 1]) {
        if (dr === 0 && dc === 0) continue;
        const value = scoreAt.get(`${row + dr}:${col + dc}`);
        if (typeof value === "number" && value > 0) values.push(value);
      }
    }
    return values.length ? values.reduce((total, value) => total + value, 0) / values.length : 0;
  };

  const { n_rows: rows, n_cols: cols } = basement.grid;
  const candidates = cells
    .filter((cell) =>
      cell.score !== null && cell.score > 0 &&
      // The perimeter ring has no full neighbourhood and sits on the imagery
      // edge, where features are least reliable.
      cell.row > 0 && cell.col > 0 && cell.row < rows - 1 && cell.col < cols - 1 &&
      known.get(`${cell.row}:${cell.col}`) === false)
    .map((cell) => {
      const nearest = mines.mines.reduce(
        (best, mine) => {
          const km = haversineKm(cell.lat, cell.lon, mine.lat, mine.lon);
          return km < best.km ? { km, mine } : best;
        },
        { km: Number.POSITIVE_INFINITY, mine: mines.mines[0]! },
      );
      return {
        ...cell,
        score: cell.score as number,
        neighbourhood: neighbourhoodOf(cell.row, cell.col),
        nearest: nearest.mine,
        km: nearest.km,
      };
    })
    // Shortlisting, not final order. Every candidate here reports the same
    // capped 0.99, so neighbourhood coherence decides which cells make the cut;
    // the classifier's margin then orders the ones that do.
    .sort((a, b) =>
      b.score - a.score ||
      b.neighbourhood - a.neighbourhood ||
      b.km - a.km);

  const chosen: typeof candidates = [];
  for (const candidate of candidates) {
    if (chosen.length === TOP_N) break;
    const clear = chosen.every(
      (other) => haversineKm(candidate.lat, candidate.lon, other.lat, other.lon) >= MIN_SEPARATION_KM,
    );
    if (clear) chosen.push(candidate);
  }

  // Refine: a 32x32 cell is ~5 x 3 km, too coarse to navigate to. Re-score the
  // winner's own cell at 8x8 and take its best sub-cell, ~350 m.
  const { cell_width_deg: width, cell_height_deg: height } = basement.grid;
  const refined = await Promise.all(
    chosen.map(async (candidate) => {
      const local = await heatmap(
        [candidate.lon - width / 2, candidate.lat - height / 2,
         candidate.lon + width / 2, candidate.lat + height / 2],
        REFINE_GRID, "geological", signal,
      );
      const best = cellsOf(local)
        .filter((cell) => cell.score !== null)
        .sort((a, b) => (b.score as number) - (a.score as number))[0];
      return {
        candidate,
        lat: best?.lat ?? candidate.lat,
        lon: best?.lon ?? candidate.lon,
        score: (best?.score as number | undefined) ?? candidate.score,
        precision_m: Math.round(local.grid.cell_height_deg * 111_320),
      };
    }),
  );

  // The score is capped at 0.99 and every target sits on it, so the list would
  // otherwise be ordered by a heuristic alone. One point query per target
  // returns the classifier's own margin, which does separate them: measured
  // 2.27 to 5.85 across these ten.
  const scored = await Promise.all(
    refined.map(async (entry) => {
      try {
        const point = await apiPost<WirePredictPoint>(
          "/predict/point",
          { lat: entry.lat, lon: entry.lon },
          { query: { mask: "none" }, timeoutMs: PREDICT_POINT_TIMEOUT_MS, signal },
        );
        return {
          ...entry,
          margin: typeof point.model_margin === "number" ? point.model_margin : null,
          rawProbability: typeof point.raw_probability === "number" ? point.raw_probability : null,
        };
      } catch {
        // A failed point query must not lose the target: it keeps its place in
        // the shortlist and reports no margin.
        return { ...entry, margin: null as number | null, rawProbability: null as number | null };
      }
    }),
  );
  // Only reorder when every margin arrived. A partial sort would mix two
  // orderings and read as neither.
  const ordered = scored.every((entry) => entry.margin !== null)
    ? [...scored].sort((a, b) => (b.margin as number) - (a.margin as number))
    : scored;

  return TargetListSchema.parse({
    provenance: {
      data_origin: "live",
      source: `Ranked from GET /prospectivity/heatmap over ${TARGET_BBOX.join(", ")} at ${TARGET_GRID}x${TARGET_GRID}, geological mask, greenfield cells only, then refined per target at ${REFINE_GRID}x${REFINE_GRID}.`,
      model_version: basement.model_version,
      generated_at: new Date().toISOString(),
    },
    bbox: TARGET_BBOX,
    mask: "geological",
    candidates_considered: candidates.length,
    min_separation_km: MIN_SEPARATION_KM,
    targets: ordered.map((entry, index) => ({
      id: `T${index + 1}`,
      rank: index + 1,
      label: `${Math.round(entry.candidate.km)} km ${bearingFrom(entry.candidate.nearest.lat, entry.candidate.nearest.lon, entry.lat, entry.lon)} of ${entry.candidate.nearest.mine_name}`,
      location: { longitude: entry.lon, latitude: entry.lat },
      score: entry.score,
      neighbourhood_score: entry.candidate.neighbourhood,
      nearest_mine: entry.candidate.nearest.mine_name,
      km_to_nearest_mine: entry.candidate.km,
      bearing_from_mine: bearingFrom(
        entry.candidate.nearest.lat, entry.candidate.nearest.lon, entry.lat, entry.lon,
      ),
      greenfield: true,
      precision_m: entry.precision_m,
      margin: entry.margin,
      raw_probability: entry.rawProbability,
    })),
  });
}
