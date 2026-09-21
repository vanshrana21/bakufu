import type mapboxgl from "mapbox-gl";
import type { FeatureCollection, Polygon } from "geojson";
import type { CellProperties } from "@/lib/api/heatmap";
import { prospectivityLayers } from "./prospectivity-layers";
import { registerMaskPattern } from "./register-mask-pattern";
import { MAP_IDS, framingPadding, type LngLatExtent } from "./sites";

/** Frames the view (first install only) and adds the prospectivity surface.
 * Idempotent, so it can run again on each `style.load`. Mines and targets are
 * DOM markers (components/explorer/map-markers.ts) and survive a style swap on
 * their own. */
export function installMapboxLayers(
  map: mapboxgl.Map,
  { surface, extent }: { surface: FeatureCollection<Polygon, CellProperties>; extent: LngLatExtent },
): void {
  // Navigation extent only; all scope membership still comes from responses.
  if (!map.getSource(MAP_IDS.surface)) {
    map.fitBounds(extent, { duration: 0, padding: framingPadding(map.getContainer().clientWidth, "initial") });
  }
  registerMaskPattern(map);
  if (!map.getSource(MAP_IDS.surface)) map.addSource(MAP_IDS.surface, { type: "geojson", data: surface });
  for (const layer of prospectivityLayers("geojson")) if (!map.getLayer(layer.id)) map.addLayer(layer);
  if (!map.getLayer(MAP_IDS.outlines)) {
    map.addLayer({
      id: MAP_IDS.outlines,
      type: "line",
      source: MAP_IDS.surface,
      paint: { "line-color": "#EACEAA", "line-width": 1, "line-opacity": 0.65 },
    });
  }
}
