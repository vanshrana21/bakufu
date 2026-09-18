/** Adapter for GET /prospectivity/heatmap.
 *
 * The backend returns a row-major score LATTICE; the map consumes a GeoJSON
 * FeatureCollection of polygons. This converts one to the other while keeping
 * the distinction the whole map depends on:
 *
 *   null  -> NO DATA (outside the imagery footprint, or every feature null).
 *            Emitted as `final_score: null`, which the committed layer filter
 *            `["==",["typeof",["get","final_score"]],"number"]` drops entirely,
 *            so it never lands on the colour ramp. Never coerce this to 0.
 *   0.0   -> a real finding: a genuine low score, or a cell a mask zeroed.
 *            Renders at the bottom of the ramp.
 */

import type { FeatureCollection, Polygon } from "geojson";
import type { MaskMode } from "@/lib/contracts";
import type { CellProperties } from "@/fixtures/prospectivity-surface";
import type { WireHeatmap } from "./wire";
import { HEATMAP_TIMEOUT_MS, apiGet } from "./client";

export interface HeatmapResult {
  surface: FeatureCollection<Polygon, CellProperties>;
  cells: WireHeatmap["cells"];
  scoreRange: WireHeatmap["score_range"];
  modelVersion: string;
  maskApplied: MaskMode;
  cached: boolean;
  generatedAt: string;
  /** True when zero-scored cells could be matched exactly to the backend's
   * `cells_masked_out` count, so the hatch overlay is exact. When false the
   * hatch is suppressed rather than guessed — see maskExclusionNote. */
  maskExclusionResolved: boolean;
  maskExclusionNote: string | null;
}

/** The backend reports mask exclusions only as an AGGREGATE count; there is no
 * per-cell flag saying "this 0.0 came from a mask". The frontend needs per-cell
 * truth to draw the exclusion hatch, because hatching a genuine low score would
 * assert a policy decision that was never made.
 *
 * Resolution: a zero-scored cell is treated as mask-excluded only when the
 * number of zero-scored cells EXACTLY equals `cells_masked_out`. Then the
 * mapping is unambiguous. Otherwise some zeros are genuine scores, the two sets
 * cannot be separated, and the hatch is suppressed with a note rather than
 * applied to cells that may not deserve it.
 */
function resolveExclusions(wire: WireHeatmap): { excluded: (value: number | null) => boolean; resolved: boolean; note: string | null } {
  if (wire.mask_applied === "none") {
    return { excluded: () => false, resolved: true, note: null };
  }
  const zeroCells = wire.scores.reduce(
    (total, row) => total + row.filter((value) => value === 0).length, 0,
  );
  if (zeroCells === wire.cells.cells_masked_out) {
    return { excluded: (value) => value === 0, resolved: true, note: null };
  }
  return {
    excluded: () => false,
    resolved: false,
    note:
      `Mask exclusions are not shown: the backend reports ${wire.cells.cells_masked_out} masked cells ` +
      `but ${zeroCells} cells scored exactly 0, so excluded cells cannot be told apart from genuine ` +
      `low scores. A per-cell mask flag on /prospectivity/heatmap would resolve this.`,
  };
}

export function adaptHeatmap(wire: WireHeatmap): HeatmapResult {
  const [minLon, , , maxLat] = wire.bbox;
  const { n_cols, n_rows, cell_width_deg, cell_height_deg } = wire.grid;
  const { excluded, resolved, note } = resolveExclusions(wire);
  const mask = (["none", "geological", "occurrence_buffer", "both"] as const).includes(wire.mask_applied as MaskMode)
    ? (wire.mask_applied as MaskMode)
    : "none";

  const features: FeatureCollection<Polygon, CellProperties>["features"] = [];
  for (let row = 0; row < n_rows; row++) {
    const values = wire.scores[row] ?? [];
    // origin is "top_left", so row 0 is the NORTHERN edge and latitude
    // decreases as the row index grows.
    const north = maxLat - row * cell_height_deg;
    const south = north - cell_height_deg;
    for (let col = 0; col < n_cols; col++) {
      const score = values[col] ?? null;
      const west = minLon + col * cell_width_deg;
      const east = west + cell_width_deg;
      const id = `cell-${row}-${col}`;
      features.push({
        type: "Feature",
        id,
        properties: {
          id,
          site_id: id,
          synthetic: false,
          // The heatmap serves post-mask scores, so raw and final agree here.
          // /predict/point is the surface that separates them per location.
          raw_score: score,
          final_score: score,
          mask_applied: mask,
          mask_excluded: excluded(score),
          scope_status: "in_scope",
        },
        geometry: {
          type: "Polygon",
          coordinates: [[[west, south], [east, south], [east, north], [west, north], [west, south]]],
        },
      });
    }
  }

  return {
    surface: { type: "FeatureCollection", features },
    cells: wire.cells,
    scoreRange: wire.score_range,
    modelVersion: wire.model_version,
    maskApplied: mask,
    cached: wire.cached,
    generatedAt: wire.generated_at,
    maskExclusionResolved: resolved,
    maskExclusionNote: note,
  };
}

export interface HeatmapQuery {
  minLon: number; minLat: number; maxLon: number; maxLat: number;
  gridSize?: number;
  mask: MaskMode;
  signal?: AbortSignal;
}

export const fetchHeatmap = (query: HeatmapQuery) =>
  apiGet<WireHeatmap>("/prospectivity/heatmap", {
    query: {
      min_lon: query.minLon, min_lat: query.minLat,
      max_lon: query.maxLon, max_lat: query.maxLat,
      grid_size: query.gridSize ?? 32, mask: query.mask,
    },
    signal: query.signal,
    // The backend documents 5s warm / 45s cold for this route alone; the shared
    // 15s default would abort a cold call that was going to succeed.
    timeoutMs: HEATMAP_TIMEOUT_MS,
  }).then(adaptHeatmap);

/** The three viewports the backend pre-warms at startup. Requesting one of
 * these first makes the demo's first paint a cache hit rather than a ~38s wait. */
export const WARM_VIEWPORTS = {
  full_bbox: { minLon: 79.0, minLat: 21.3, maxLon: 80.6, maxLat: 22.1 },
  balaghat_bhandara: { minLon: 79.53, minLat: 21.32, maxLon: 80.57, maxLat: 22.05 },
  balaghat_ukwa: { minLon: 80.05, minLat: 21.7, maxLon: 80.6, maxLat: 22.05 },
} as const;
