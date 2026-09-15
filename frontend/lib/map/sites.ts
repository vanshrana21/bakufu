/** Pure site geometry shared by both map renderers (Mapbox and MapLibre).
 *
 * Everything here is camera framing and drawing input. None of it is a scope
 * decision: Sausar scope and buffer membership always come from the fixture or
 * the backend response, never from where a point happens to sit on the map.
 */

import type { FeatureCollection, Point } from "geojson";
import type { SiteFixture } from "@/fixtures/predictions";

/** Source and layer ids both renderers use, so the legend, E2E counts and click
 * handling agree on what a "waste site" layer is. */
export const MAP_IDS = {
  sites: "fixture-sites",
  diagnosticLayer: "fixture-site-points",
  wasteLayer: "fixture-waste-sites",
  selectionLayer: "site-selection",
  surface: "prediction-cells",
  outlines: "prediction-outlines",
  wasteIcon: "waste-diamond",
} as const;

export interface SiteProperties {
  id: string;
  name: string;
  waste: boolean;
}

export const isWasteAsset = (site: SiteFixture): boolean =>
  site.asset_type === "historical_waste_dump" || site.asset_type === "slag_heap";

/** In-scope sites with coordinates, as map points. Out-of-scope and unlocated
 * sites are never drawn. */
export function siteFeatures(sites: readonly SiteFixture[]): FeatureCollection<Point, SiteProperties> {
  return {
    type: "FeatureCollection",
    features: sites.flatMap((site) =>
      site.location && site.scope_status === "in_scope"
        ? [{
          type: "Feature" as const,
          id: site.id,
          geometry: { type: "Point" as const, coordinates: [site.location.longitude, site.location.latitude] },
          properties: { id: site.id, name: site.name, waste: isWasteAsset(site) },
        }]
        : [],
    ),
  };
}

/** Degrees added around each site when framing, so markers never sit on the edge. */
const FRAME_PAD = { longitude: 0.08, latitude: 0.07 };

export type LngLatExtent = [[number, number], [number, number]];

/** South-west and north-east corners around the located sites, or null when
 * there is nothing to frame. `inScopeOnly` restricts it to drawable sites. */
export function siteExtent(sites: readonly SiteFixture[], { inScopeOnly }: { inScopeOnly: boolean }): LngLatExtent | null {
  let west = Infinity, south = Infinity, east = -Infinity, north = -Infinity;
  for (const site of sites) {
    if (!site.location || (inScopeOnly && site.scope_status !== "in_scope")) continue;
    west = Math.min(west, site.location.longitude - FRAME_PAD.longitude);
    east = Math.max(east, site.location.longitude + FRAME_PAD.longitude);
    south = Math.min(south, site.location.latitude - FRAME_PAD.latitude);
    north = Math.max(north, site.location.latitude + FRAME_PAD.latitude);
  }
  return Number.isFinite(west) ? [[west, south], [east, north]] : null;
}

/** Camera padding in pixels. The first frame leaves room for the toolbar; a
 * user-requested refit also clears the legend. Narrow maps reserve more bottom. */
export function framingPadding(containerWidth: number, purpose: "initial" | "refit") {
  const narrow = containerWidth < 600;
  return purpose === "initial"
    ? { top: 80, bottom: narrow ? 150 : 42, left: 35, right: 45 }
    : { top: 90, bottom: narrow ? 170 : 75, left: 35, right: 45 };
}

/** Where a site sits on the no-WebGL coordinate plot, as CSS percentages. */
export function fallbackPlotPosition(site: SiteFixture): { left: string; top: string } | null {
  if (!site.location) return null;
  const left = 18 + ((site.location.longitude - 79.15) / (80.15 - 79.15)) * 64;
  const top = 76 - ((site.location.latitude - 21.45) / (21.95 - 21.45)) * 52;
  return {
    left: `${Math.max(10, Math.min(86, left))}%`,
    top: `${Math.max(16, Math.min(82, top))}%`,
  };
}

interface RenderedFeature {
  properties?: { [name: string]: unknown } | null;
}

/** Features each engine actually drew, counted by unique site/cell id. Exposed as
 * data attributes for accessible diagnostics and E2E, not just the input counts. */
export function renderedCounts(
  query: (layers: string[]) => readonly RenderedFeature[],
  hasLayer: (id: string) => boolean,
): { cells: number; excluded: number; waste: number } {
  const count = (layers: string[]) => {
    const present = layers.filter(hasLayer);
    return present.length === 0 ? 0 : new Set(query(present).map((feature) => feature.properties?.id)).size;
  };
  return {
    cells: count(["prospectivity-screened", "prospectivity-excluded"]),
    excluded: count(["prospectivity-excluded"]),
    waste: count([MAP_IDS.wasteLayer]),
  };
}

export const sameCounts = (a: ReturnType<typeof renderedCounts>, b: ReturnType<typeof renderedCounts>) =>
  a.cells === b.cells && a.excluded === b.excluded && a.waste === b.waste;

/** The floating name tag drawn above the selected site. */
export function siteLabelElement(name: string): HTMLSpanElement {
  const label = document.createElement("span");
  label.className = "map-site-label";
  label.textContent = name;
  return label;
}

/** Marker placement for the name tag, shared so both engines put it in the same spot. */
export const SITE_LABEL_MARKER = { anchor: "bottom" as const, offset: [0, -22] as [number, number] };

export const prefersReducedMotion = () =>
  typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
