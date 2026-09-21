/** Pure point geometry shared by both map renderers (Mapbox and MapLibre).
 *
 * Everything here is camera framing and drawing input. None of it is a scope
 * decision: Sausar scope and mask membership always come from the backend
 * response, never from where a point happens to sit on the map.
 */

/** Source and layer ids both renderers use, so the legend, E2E counts and
 * draw calls agree on what the prospectivity surface is. */
export const MAP_IDS = {
  surface: "prediction-cells",
  outlines: "prediction-outlines",
} as const;

/** Anything the map places by coordinate: a mine or a model target. */
export interface Located {
  location: { longitude: number; latitude: number };
}

export type LngLat = [number, number];
export type LngLatExtent = [LngLat, LngLat];

/** Every marker position as lon/lat, mines first. */
export function markerPoints(mines: readonly Located[], targets: readonly Located[]): LngLat[] {
  return [...mines, ...targets].map((point) => [point.location.longitude, point.location.latitude]);
}

/** Degrees added around the markers when framing, so none sits on the edge. */
const FRAME_PAD = { longitude: 0.08, latitude: 0.07 };

/** South-west and north-east corners around the points, or null when there is
 * nothing to frame. */
export function pointsExtent(points: readonly LngLat[]): LngLatExtent | null {
  let west = Infinity, south = Infinity, east = -Infinity, north = -Infinity;
  for (const [longitude, latitude] of points) {
    west = Math.min(west, longitude - FRAME_PAD.longitude);
    east = Math.max(east, longitude + FRAME_PAD.longitude);
    south = Math.min(south, latitude - FRAME_PAD.latitude);
    north = Math.max(north, latitude + FRAME_PAD.latitude);
  }
  return Number.isFinite(west) ? [[west, south], [east, north]] : null;
}

/** The viewport the surface is served over. The targets are drawn from it, so
 * framing it shows them all even before they arrive. */
export const BELT_EXTENT: LngLatExtent = [[79.0, 21.3], [80.6, 22.1]];

/** The first frame: the whole served belt, widened to any marker outside it
 * (Gumgaon sits at 78.98 E). The targets stream in after the map loads, so
 * framing only the markers present at load would crop them. */
export function initialExtent(points: readonly LngLat[]): LngLatExtent {
  const markers = pointsExtent(points);
  if (!markers) return BELT_EXTENT;
  const [[west, south], [east, north]] = BELT_EXTENT;
  return [
    [Math.min(west, markers[0][0]), Math.min(south, markers[0][1])],
    [Math.max(east, markers[1][0]), Math.max(north, markers[1][1])],
  ];
}

/** Camera padding in pixels. The first frame leaves room for the toolbar; a
 * user-requested refit also clears the legend. Narrow maps reserve more bottom. */
export function framingPadding(containerWidth: number, purpose: "initial" | "refit") {
  const narrow = containerWidth < 600;
  return purpose === "initial"
    ? { top: 80, bottom: narrow ? 150 : 42, left: 35, right: 45 }
    : { top: 90, bottom: narrow ? 170 : 75, left: 35, right: 45 };
}

/** The no-WebGL coordinate plot's frame: the served belt, widened just enough
 * to hold Gumgaon at 78.98 E. */
export const PLOT_EXTENT: LngLatExtent = [[78.9, 21.25], [80.7, 22.15]];

/** Where a point sits on the no-WebGL coordinate plot, as CSS percentages. The
 * frame is drawn at 18-82% across and 24-76% down; a point outside it is
 * clamped to the edge rather than lost. */
export function fallbackPlotPosition(point: Located): { left: string; top: string } {
  const [[west, south], [east, north]] = PLOT_EXTENT;
  const left = 18 + ((point.location.longitude - west) / (east - west)) * 64;
  const top = 76 - ((point.location.latitude - south) / (north - south)) * 52;
  return {
    left: `${Math.max(10, Math.min(90, left))}%`,
    top: `${Math.max(16, Math.min(84, top))}%`,
  };
}

interface RenderedFeature {
  properties?: { [name: string]: unknown } | null;
}

/** Cells each engine actually drew, counted by unique cell id. Exposed as data
 * attributes for accessible diagnostics and E2E, not just the input counts. */
export function renderedCounts(
  query: (layers: string[]) => readonly RenderedFeature[],
  hasLayer: (id: string) => boolean,
): { cells: number; excluded: number } {
  const count = (layers: string[]) => {
    const present = layers.filter(hasLayer);
    return present.length === 0 ? 0 : new Set(query(present).map((feature) => feature.properties?.id)).size;
  };
  return {
    cells: count(["prospectivity-screened", "prospectivity-excluded"]),
    excluded: count(["prospectivity-excluded"]),
  };
}

export const sameCounts = (a: ReturnType<typeof renderedCounts>, b: ReturnType<typeof renderedCounts>) =>
  a.cells === b.cells && a.excluded === b.excluded;

export const prefersReducedMotion = () =>
  typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
