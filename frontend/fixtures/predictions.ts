import type { MaskMode, PredictionResponse } from "@/lib/contracts";
import { PredictionResponseSchema } from "@/lib/contracts";

export interface SiteFixture {
  id: string;
  name: string;
  location: PredictionResponse["location"];
  asset_type: PredictionResponse["asset"]["asset_type"];
  scope_status: PredictionResponse["scope_status"];
  inside_buffer: boolean | null;
  geological_pass: boolean | null;
  raw_score: number | null;
  synthetic: boolean;
}

/** No waste inventory is supplied in PROJECT_STATE. These waste locations and
 * memberships are SYNTHETIC UI examples, not identified waste reserves.
 * Sandur/Bonai are explicit scope fixtures, not a general geofencing algorithm.
 */
export const DEMO_SITES: readonly SiteFixture[] = [
  { id: "demo-dump-a", name: "Demo waste dump A", location: { longitude: 79.52, latitude: 21.73 }, asset_type: "historical_waste_dump", scope_status: "in_scope", inside_buffer: true, geological_pass: true, raw_score: 0.84, synthetic: true },
  { id: "demo-slag-b", name: "Demo slag heap B", location: { longitude: 80.05, latitude: 21.82 }, asset_type: "slag_heap", scope_status: "in_scope", inside_buffer: true, geological_pass: true, raw_score: 0.62, synthetic: true },
  { id: "demo-dump-c", name: "Demo waste dump C · outside buffer", location: { longitude: 79.25, latitude: 21.65 }, asset_type: "historical_waste_dump", scope_status: "in_scope", inside_buffer: false, geological_pass: true, raw_score: 0.76, synthetic: true },
  { id: "farmland-control", name: "Farmland diagnostic · north of Nagpur", location: { longitude: 79.30, latitude: 21.55 }, asset_type: "diagnostic_point", scope_status: "in_scope", inside_buffer: false, geological_pass: true, raw_score: 0.99, synthetic: false },
  { id: "sandur", name: "Sandur", location: null, asset_type: "place", scope_status: "out_of_scope", inside_buffer: null, geological_pass: null, raw_score: null, synthetic: false },
  { id: "bonai", name: "Bonai", location: null, asset_type: "place", scope_status: "out_of_scope", inside_buffer: null, geological_pass: null, raw_score: null, synthetic: false },
];

export function isGhostReserveCandidate(site: SiteFixture): boolean {
  // GHOST RESERVE FILTER: waste asset ∩ inside verified 5km union ∩ model scope.
  // Mock membership is seeded. Live membership must come from backend PostGIS
  // metric-distance geometry; do not approximate kilometres using degrees.
  return (site.asset_type === "historical_waste_dump" || site.asset_type === "slag_heap") &&
    site.inside_buffer === true && site.scope_status === "in_scope";
}

export function buildPredictionFixture(siteId: string, mask: MaskMode): PredictionResponse {
  const site = DEMO_SITES.find((s) => s.id === siteId);
  if (!site) throw new Error("No fixture exists for this location. A live point-query API is required.");
  const common = {
    prediction_id: `fixture:${site.id}:${mask}`,
    provenance: {
      data_origin: "fixture" as const,
      source: site.synthetic ? "Synthetic UI fixture; not a verified waste inventory" : "Project-state diagnostic adapted into a mock response",
      model_version: "mock-v6-interface",
      generated_at: "2026-09-08T00:00:00Z",
    },
    asset: {
      id: site.id, name: site.name, asset_type: site.asset_type,
      inventory_status: site.synthetic ? "synthetic" as const : "documented" as const,
      assay_status: site.asset_type === "historical_waste_dump" || site.asset_type === "slag_heap" ? "pending" as const : "not_applicable" as const,
      occurrence_buffer_membership: site.inside_buffer === null ? "unknown" as const : site.inside_buffer ? "inside" as const : "outside" as const,
    },
    location: site.location,
    validated_scope: "Sausar Belt" as const,
    mask_requested: mask,
  };
  // SAUSAR SCOPE GATE: execute BEFORE inference and before any score is returned.
  // Live mode must use the backend's versioned validated-domain predicate.
  // A bounding box or a blacklist of two town names is not sufficient.
  if (site.scope_status !== "in_scope") {
    return PredictionResponseSchema.parse({ ...common, scope_status: site.scope_status,
      scope_reason: "Outside validated scope (Sausar Belt)", raw_score: null, final_score: null,
      mask_applied: "none", mask_results: [], shap: null,
      interpretation: "The model is not validated for this belt. No absence-of-manganese conclusion is made.",
    });
  }
  const maskResults: PredictionResponse["mask_results"] = [];
  if (mask === "geological" || mask === "both") maskResults.push({
    mask: "geological", outcome: site.geological_pass === null ? "unknown" : site.geological_pass ? "passed" : "excluded",
    reason: "Fixture geological membership; live system uses a coarse Macrostrat 1:5M proxy.",
    source: "Mock membership; GSI 1:50K is not available in the supplied state",
  });
  if (mask === "occurrence_buffer" || mask === "both") maskResults.push({
    mask: "occurrence_buffer", outcome: site.inside_buffer === null ? "unknown" : site.inside_buffer ? "passed" : "excluded",
    reason: site.inside_buffer ? "Inside the 5km occurrence-buffer union in this fixture." : "Outside the 5km occurrence-buffer union in this fixture.",
    source: "Mock membership; live mask is the union around 191 occurrences",
  });
  const excluded = maskResults.some((m) => m.outcome === "excluded");
  const unresolved = maskResults.some((m) => m.outcome === "unknown");
  return PredictionResponseSchema.parse({ ...common, scope_status: "in_scope",
    scope_reason: "Within Sausar geographic scope in this fixture; waste-material transfer is not validated.",
    raw_score: site.raw_score, final_score: excluded ? 0 : unresolved ? null : site.raw_score,
    mask_applied: mask, mask_results: maskResults,
    interpretation: excluded ? "Excluded by screening policy. This is not evidence of manganese absence."
      : "Screening example only. Waste assays, process recovery and environmental review are still required.",
    shap: site.synthetic ? {
      output_scale: "raw_margin", explains: "underlying_classifier_before_pu_adjustment_and_masks", base_value: -0.35,
      contributions: [
        { feature: "ae_12", label: "Learned surface pattern", value: 0.42, contribution: 0.73 },
        { feature: "elevation", label: "Elevation", value: 520, contribution: 0.36 },
        { feature: "mn_ratio_swir", label: "SWIR band ratio", value: 1.18, contribution: 0.21 },
        { feature: "ndvi", label: "Vegetation index", value: 0.28, contribution: -0.16 },
      ],
    } : null,
  });
}
