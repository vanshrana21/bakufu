import type { FeatureCollection, Polygon } from "geojson";
import type { MaskMode, PredictionResponse } from "@/lib/contracts";
import { buildPredictionFixture, type SiteFixture } from "./predictions";

export interface CellProperties {
  // `synthetic` is boolean, not a literal true: the same cell shape now carries
  // live /prospectivity/heatmap output as well as these fixture blobs.
  id: string; site_id: string; synthetic: boolean;
  raw_score: number | null; final_score: number | null;
  mask_applied: MaskMode; mask_excluded: boolean;
  scope_status: PredictionResponse["scope_status"];
}

/** Deliberately synthetic display cells around fixture locations.
 * These are neither dump footprints nor a 5km buffer nor a validated belt.
 * Membership and score semantics come from the same response as the inspector.
 * Production replacement: versioned prediction-cell tiles + surveyed inventory.
 */
export function buildProspectivitySurface(sites: readonly SiteFixture[], mask: MaskMode): FeatureCollection<Polygon, CellProperties> {
  return { type: "FeatureCollection", features: sites.flatMap((site) => {
    if (!site.location || site.scope_status !== "in_scope") return [];
    const prediction = buildPredictionFixture(site.id, mask);
    const x = site.location.longitude, y = site.location.latitude;
    return [{
      type: "Feature" as const, id: site.id,
      properties: { id: site.id, site_id: site.id, synthetic: true as const,
        raw_score: prediction.raw_score, final_score: prediction.final_score,
        mask_applied: prediction.mask_applied, scope_status: prediction.scope_status,
        mask_excluded: prediction.mask_results.some((result) => result.outcome === "excluded"),
      },
      geometry: { type: "Polygon" as const, coordinates: [[
        [x - .055, y - .025], [x - .075, y + .005], [x - .04, y + .04],
        [x + .01, y + .055], [x + .065, y + .02], [x + .05, y - .035],
        [x + .005, y - .05], [x - .055, y - .025],
      ]] },
    }];
  }) };
}
