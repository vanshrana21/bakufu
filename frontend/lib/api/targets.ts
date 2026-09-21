/** The model's top greenfield exploration targets, derived from the served heatmap.
 *
 * There is no "top targets" endpoint. This composes two browser-proxied routes
 * and the mine list the page hands down from the server:
 *
 *   1. GET /prospectivity/heatmap mask=geological         candidate ground, basement only
 *   2. GET /prospectivity/heatmap mask=occurrence_buffer  which cells are already known
 *   3. the ten MOIL mines                                  (props; the browser never calls /mines)
 *
 * then refines each winner with a small local heatmap over its own cell (to ~±320 m), and
 * orders the ten by the classifier's own margin from POST /predict/point.
 *
 * Why the ranking is not simply "highest score": close to two hundred of the
 * 1,024 cells sit at the 0.99 cap, so score alone is a many-way tie ordered by
 * array position. Two measured criteria break it:
 *
 *   - greenfield only. A cell inside the 5 km occurrence buffer is ground
 *     somebody already found; it cannot be a new prediction.
 *   - neighbourhood coherence. A cap-scoring cell whose eight neighbours also
 *     score high is a coherent anomaly; a lone hot pixel beside cold ground is
 *     more likely noise.
 *
 * Those shortlist. The order of the ten comes from the classifier margin at each
 * refined point, because the served score is capped and every target sits on it.
 * If any margin fails to arrive the shortlist keeps its coherence order and says
 * so: a partial sort would mix two orderings and read as neither.
 *
 * Ported from the team lead's Explorer (yashnimde-ship-it/Spin-off, 2026-09-17).
 */

import type { MaskMode, MineLocation, TargetList } from "@/lib/contracts";
import { TargetListSchema } from "@/lib/contracts";
import type { WireHeatmap } from "./wire";
import { HEATMAP_TIMEOUT_MS, PREDICT_POINT_TIMEOUT_MS, apiGet, apiPost } from "./client";
import { parseWire, WireHeatmapSchema, WirePredictPointSchema } from "./wire-schemas";

/** The pre-warmed belt viewport: a cold heatmap is ~38s, a warm one is instant. */
export const TARGET_BBOX: [number, number, number, number] = [79.0, 21.3, 80.6, 22.1];
export const TARGET_GRID = 32;
/** 8 is the backend minimum; over one cell it lands at ~650 × 350 m. */
export const REFINE_GRID = 8;
/** Without a floor, ten cells of one anomaly would fill the list. */
export const MIN_SEPARATION_KM = 10;
export const TOP_N = 10;

const COMPASS = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"] as const;
type Compass = (typeof COMPASS)[number];

export function haversineKm(lat1: number, lon1: number, lat2: number, lon2: number): number {
  const radius = 6371.0088;
  const p1 = (lat1 * Math.PI) / 180;
  const p2 = (lat2 * Math.PI) / 180;
  const dp = p2 - p1;
  const dl = ((lon2 - lon1) * Math.PI) / 180;
  const a = Math.sin(dp / 2) ** 2 + Math.cos(p1) * Math.cos(p2) * Math.sin(dl / 2) ** 2;
  return 2 * radius * Math.asin(Math.sqrt(a));
}

/** The compass direction from the first point to the second. */
export function bearingFrom(lat1: number, lon1: number, lat2: number, lon2: number): Compass {
  const p1 = (lat1 * Math.PI) / 180;
  const p2 = (lat2 * Math.PI) / 180;
  const dl = ((lon2 - lon1) * Math.PI) / 180;
  const y = Math.sin(dl) * Math.cos(p2);
  const x = Math.cos(p1) * Math.sin(p2) - Math.sin(p1) * Math.cos(p2) * Math.cos(dl);
  const degrees = ((Math.atan2(y, x) * 180) / Math.PI + 360) % 360;
  return COMPASS[Math.floor((degrees + 22.5) / 45) % 8]!;
}

export interface Cell { row: number; col: number; lat: number; lon: number; score: number | null }

/** How far a cell centre can be from any point in its cell along either axis:
 * half the longer side, in metres. A cell is wider than it is tall here (a
 * degree of longitude is shorter than one of latitude only by cos(lat)), so
 * quoting half the height alone would overstate the precision east-west. */
export function halfCellMetres(widthDeg: number, heightDeg: number, lat: number): number {
  const metresPerDegree = 111_320;
  const width = widthDeg * metresPerDegree * Math.cos((lat * Math.PI) / 180);
  const height = heightDeg * metresPerDegree;
  return Math.round(Math.max(width, height) / 2);
}

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

const heatmap = (bbox: readonly number[], gridSize: number, mask: MaskMode, signal?: AbortSignal) =>
  apiGet<unknown>("/prospectivity/heatmap", {
    query: { min_lon: bbox[0], min_lat: bbox[1], max_lon: bbox[2], max_lat: bbox[3], grid_size: gridSize, mask },
    timeoutMs: HEATMAP_TIMEOUT_MS,
    signal,
  }).then((raw) => parseWire(WireHeatmapSchema, raw, "/prospectivity/heatmap"));

export interface Candidate extends Cell {
  score: number;
  neighbourhood: number;
  nearest: MineLocation;
  km: number;
}

/** The greenfield shortlist, before refinement: basement cells outside every
 * known 5 km buffer, off the imagery edge, ordered by score, then neighbourhood
 * coherence, then distance from the nearest mine, and thinned to TOP_N cells at
 * least MIN_SEPARATION_KM apart. Pure, so it is tested on its own. */
export function shortlist(basement: WireHeatmap, buffered: WireHeatmap, mines: readonly MineLocation[]): {
  candidates: Candidate[];
  chosen: Candidate[];
} {
  if (mines.length === 0) return { candidates: [], chosen: [] };

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
  const candidates: Candidate[] = cells
    .filter((cell) =>
      cell.score !== null && cell.score > 0 &&
      // The perimeter ring has no full neighbourhood and sits on the imagery
      // edge, where features are least reliable.
      cell.row > 0 && cell.col > 0 && cell.row < rows - 1 && cell.col < cols - 1 &&
      known.get(`${cell.row}:${cell.col}`) === false)
    .map((cell) => {
      const nearest = mines.reduce(
        (best, mine) => {
          const km = haversineKm(cell.lat, cell.lon, mine.location.latitude, mine.location.longitude);
          return km < best.km ? { km, mine } : best;
        },
        { km: Number.POSITIVE_INFINITY, mine: mines[0]! },
      );
      return { ...cell, score: cell.score as number, neighbourhood: neighbourhoodOf(cell.row, cell.col), nearest: nearest.mine, km: nearest.km };
    })
    .sort((a, b) => b.score - a.score || b.neighbourhood - a.neighbourhood || b.km - a.km);

  const chosen: Candidate[] = [];
  for (const candidate of candidates) {
    if (chosen.length === TOP_N) break;
    if (chosen.every((other) => haversineKm(candidate.lat, candidate.lon, other.lat, other.lon) >= MIN_SEPARATION_KM)) {
      chosen.push(candidate);
    }
  }
  return { candidates, chosen };
}

export async function fetchTopTargets(mines: readonly MineLocation[], signal?: AbortSignal): Promise<TargetList> {
  const [basement, buffered] = await Promise.all([
    heatmap(TARGET_BBOX, TARGET_GRID, "geological", signal),
    heatmap(TARGET_BBOX, TARGET_GRID, "occurrence_buffer", signal),
  ]);
  const { candidates, chosen } = shortlist(basement, buffered, mines);

  // Refine: a 32x32 cell is ~5 x 3 km, too coarse to navigate to. Re-score the
  // winner's own cell at 8x8 and take its best sub-cell, ~650 x 350 m.
  const { cell_width_deg: width, cell_height_deg: height } = basement.grid;
  const refined = await Promise.all(
    chosen.map(async (candidate) => {
      try {
        const local = await heatmap(
          [candidate.lon - width / 2, candidate.lat - height / 2, candidate.lon + width / 2, candidate.lat + height / 2],
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
          precision_m: halfCellMetres(local.grid.cell_width_deg, local.grid.cell_height_deg, best?.lat ?? candidate.lat),
        };
      } catch {
        // An unrefined target keeps its cell centre and says so through precision.
        return { candidate, lat: candidate.lat, lon: candidate.lon, score: candidate.score, precision_m: halfCellMetres(width, height, candidate.lat) };
      }
    }),
  );

  // One point query per target returns the classifier's own margin, which does
  // separate targets that all read 0.99 once capped.
  const scored = await Promise.all(
    refined.map(async (entry) => {
      try {
        const raw = await apiPost<unknown>(
          "/predict/point",
          { lat: entry.lat, lon: entry.lon },
          { query: { mask: "none" }, timeoutMs: PREDICT_POINT_TIMEOUT_MS, signal },
        );
        const point = parseWire(WirePredictPointSchema, raw, "/predict/point");
        return { ...entry, margin: point.model_margin ?? null, rawProbability: point.raw_probability ?? null, error: null as string | null };
      } catch (error) {
        if (signal?.aborted) throw error;
        // A failed point query must not lose the target: it keeps its place in
        // the shortlist and reports no margin.
        return { ...entry, margin: null as number | null, rawProbability: null as number | null, error: error instanceof Error ? error.message : "point query failed" };
      }
    }),
  );

  const allMargins = scored.length > 0 && scored.every((entry) => entry.margin !== null);
  const ordered = allMargins ? [...scored].sort((a, b) => (b.margin as number) - (a.margin as number)) : scored;
  const firstError = scored.find((entry) => entry.error)?.error ?? null;

  return TargetListSchema.parse({
    provenance: {
      data_origin: "live",
      source:
        `GET /prospectivity/heatmap over ${TARGET_BBOX.join(", ")} at ${TARGET_GRID}×${TARGET_GRID}, geological mask, ` +
        `greenfield cells only; each target refined at ${REFINE_GRID}×${REFINE_GRID} over its own cell.`,
      model_version: basement.model_version,
      generated_at: new Date().toISOString(),
    },
    bbox: TARGET_BBOX,
    candidates_considered: candidates.length,
    min_separation_km: MIN_SEPARATION_KM,
    ranking: allMargins ? "classifier_margin" : "neighbourhood_coherence",
    ranking_note: allMargins
      ? "Ordered by the classifier's margin at each refined point; the served score is capped at 0.99 and every target reaches it."
      : `Ordered by neighbourhood coherence: classifier margins did not arrive for every target${firstError ? ` (${firstError})` : ""}.`,
    targets: ordered.map((entry, index) => {
      const bearing = bearingFrom(entry.candidate.nearest.location.latitude, entry.candidate.nearest.location.longitude, entry.lat, entry.lon);
      return {
        id: `T${index + 1}`,
        rank: index + 1,
        label: `${Math.round(entry.candidate.km)} km ${bearing} of ${entry.candidate.nearest.name}`,
        location: { longitude: entry.lon, latitude: entry.lat },
        score: Math.min(entry.score, 0.99),
        neighbourhood_score: Math.min(entry.candidate.neighbourhood, 1),
        nearest_mine: entry.candidate.nearest.name,
        km_to_nearest_mine: entry.candidate.km,
        bearing_from_mine: bearing,
        precision_m: entry.precision_m,
        margin: entry.margin,
        raw_probability: entry.rawProbability,
      };
    }),
  });
}
