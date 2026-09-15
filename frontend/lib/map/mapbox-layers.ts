import mapboxgl from "mapbox-gl";
import type { FeatureCollection, Polygon } from "geojson";
import type { SiteFixture } from "@/fixtures/predictions";
import type { CellProperties } from "@/fixtures/prospectivity-surface";
import { prospectivityLayers } from "./prospectivity-layers";
import { registerMaskPattern } from "./register-mask-pattern";
import { MAP_IDS, framingPadding, siteExtent, siteFeatures } from "./sites";

/** Draws the waste-site diamond into the style's sprite once. */
function addWasteDiamond(map: mapboxgl.Map): void {
  if (map.hasImage(MAP_IDS.wasteIcon)) return;
  const icon = document.createElement("canvas");
  icon.width = 28;
  icon.height = 28;
  const context = icon.getContext("2d");
  if (!context) return;
  context.beginPath();
  context.moveTo(14, 3);
  context.lineTo(25, 14);
  context.lineTo(14, 25);
  context.lineTo(3, 14);
  context.closePath();
  context.fillStyle = "#34150F";
  context.fill();
  context.strokeStyle = "#EACEAA";
  context.lineWidth = 2;
  context.stroke();
  map.addImage(
    MAP_IDS.wasteIcon,
    { width: 28, height: 28, data: new Uint8Array(context.getImageData(0, 0, 28, 28).data) },
    { pixelRatio: 2 },
  );
}

/** Frames the sites (first install only) and adds every source and layer the
 * Explorer draws. Idempotent, so it can run again on each `style.load`. */
export function installMapboxLayers(
  map: mapboxgl.Map,
  { sites, surface }: { sites: readonly SiteFixture[]; surface: FeatureCollection<Polygon, CellProperties> },
): void {
  // Navigation extent only; all scope membership still comes from responses.
  if (!map.getSource(MAP_IDS.sites)) {
    const extent = siteExtent(sites, { inScopeOnly: false });
    if (extent) {
      map.fitBounds(extent, { duration: 0, padding: framingPadding(map.getContainer().clientWidth, "initial") });
    }
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
  if (!map.getSource(MAP_IDS.sites)) {
    map.addSource(MAP_IDS.sites, { type: "geojson", data: siteFeatures(sites), promoteId: "id" });
  }
  addWasteDiamond(map);
  if (!map.getLayer(MAP_IDS.selectionLayer)) {
    map.addLayer({
      id: MAP_IDS.selectionLayer,
      type: "circle",
      source: MAP_IDS.sites,
      paint: {
        "circle-radius": 15,
        "circle-color": "#85431E",
        "circle-opacity": ["case", ["boolean", ["feature-state", "selected"], false], 0.85, 0],
        "circle-stroke-color": "#D39858",
        "circle-stroke-width": 2,
        "circle-stroke-opacity": ["case", ["boolean", ["feature-state", "selected"], false], 1, 0],
      },
    });
  }
  if (!map.getLayer(MAP_IDS.diagnosticLayer)) {
    map.addLayer({
      id: MAP_IDS.diagnosticLayer,
      type: "circle",
      source: MAP_IDS.sites,
      filter: ["==", ["get", "waste"], false],
      paint: { "circle-radius": 6, "circle-color": "#EACEAA", "circle-stroke-color": "#EACEAA", "circle-stroke-width": 1 },
    });
  }
  if (!map.getLayer(MAP_IDS.wasteLayer) && map.hasImage(MAP_IDS.wasteIcon)) {
    map.addLayer({
      id: MAP_IDS.wasteLayer,
      type: "symbol",
      source: MAP_IDS.sites,
      filter: ["==", ["get", "waste"], true],
      layout: { "icon-image": MAP_IDS.wasteIcon, "icon-size": 1.2, "icon-allow-overlap": true },
    });
  }
  // Mock footprint geometry only. Replace this source with versioned vector
  // tiles when supplied; retain the same layer specs and null-score gates.
}
