import type * as maplibregl from "maplibre-gl";
import type { FillLayerSpecification } from "maplibre-gl";
import type { FeatureCollection, Polygon } from "geojson";
import type { SiteFixture } from "@/fixtures/predictions";
import type { CellProperties } from "@/fixtures/prospectivity-surface";
import { prospectivityLayers } from "./prospectivity-layers";
import { registerMaskPattern } from "./register-mask-pattern";
import { MAP_IDS, framingPadding, siteExtent, siteFeatures } from "./sites";

/** NASA GIBS context source. Geographic context only, never model input. */
export const NASA_CONTEXT_SOURCE = "nasa-context";

/** A 32x32 diamond sprite built from pixels, so marker rendering never depends
 * on a remote glyph or sprite service. */
function wasteDiamondPixels(): { width: number; height: number; data: Uint8Array } {
  const width = 32;
  const data = new Uint8Array(width * width * 4);
  for (let y = 0; y < width; y++) {
    for (let x = 0; x < width; x++) {
      const distance = Math.abs(x - 15.5) + Math.abs(y - 15.5);
      if (distance > 14) continue;
      data.set(distance > 10 ? [234, 206, 170, 255] : [52, 21, 15, 255], (y * width + x) * 4);
    }
  }
  return { width, height: width, data };
}

/** Frames the sites and adds every Explorer source and layer, then the NASA
 * context imagery beneath the prospectivity fill. Runs once, on `load`. */
export function installMaplibreLayers(
  map: maplibregl.Map,
  { sites, surface }: { sites: readonly SiteFixture[]; surface: FeatureCollection<Polygon, CellProperties> },
): void {
  // Fit display fixtures for this viewport, never treat camera bounds as scope.
  const extent = siteExtent(sites, { inScopeOnly: false });
  if (extent && !map.getSource(MAP_IDS.sites)) map.fitBounds(extent, { duration: 0, padding: framingPadding(map.getContainer().clientWidth, "initial") });

  registerMaskPattern(map);
  if (!map.getSource(MAP_IDS.surface)) map.addSource(MAP_IDS.surface, { type: "geojson", data: surface });
  // Both engines implement these standard v8 fill expressions. Narrow cast
  // stays at the adapter boundary; no Mapbox-only paint properties are used.
  for (const layer of prospectivityLayers("geojson")) if (!map.getLayer(layer.id)) map.addLayer(layer as FillLayerSpecification);
  if (!map.getLayer(MAP_IDS.outlines)) map.addLayer({
    id: MAP_IDS.outlines,
    type: "line",
    source: MAP_IDS.surface,
    paint: { "line-color": "#EACEAA", "line-width": 1, "line-opacity": 0.8 },
  });
  if (!map.getSource(MAP_IDS.sites)) map.addSource(MAP_IDS.sites, { type: "geojson", data: siteFeatures(sites), promoteId: "id" });
  if (!map.hasImage(MAP_IDS.wasteIcon)) map.addImage(MAP_IDS.wasteIcon, wasteDiamondPixels(), { pixelRatio: 2 });
  if (!map.getLayer(MAP_IDS.selectionLayer)) map.addLayer({
    id: MAP_IDS.selectionLayer,
    type: "circle",
    source: MAP_IDS.sites,
    paint: {
      "circle-radius": 15,
      "circle-color": "#85431E",
      "circle-stroke-color": "#D39858",
      "circle-stroke-width": 2,
      "circle-opacity": ["case", ["boolean", ["feature-state", "selected"], false], 0.8, 0],
      "circle-stroke-opacity": ["case", ["boolean", ["feature-state", "selected"], false], 1, 0],
    },
  });
  if (!map.getLayer(MAP_IDS.diagnosticLayer)) map.addLayer({
    id: MAP_IDS.diagnosticLayer,
    type: "circle",
    source: MAP_IDS.sites,
    filter: ["==", ["get", "waste"], false],
    paint: { "circle-radius": 6, "circle-color": "#EACEAA", "circle-stroke-width": 2, "circle-stroke-color": "#85431E" },
  });
  if (!map.getLayer(MAP_IDS.wasteLayer)) map.addLayer({
    id: MAP_IDS.wasteLayer,
    type: "symbol",
    source: MAP_IDS.sites,
    filter: ["==", ["get", "waste"], true],
    layout: { "icon-image": MAP_IDS.wasteIcon, "icon-size": 1.3, "icon-allow-overlap": true },
  });
}

/** Low-resolution NASA Blue Marble tiles under the screening layers. */
export function addNasaContext(map: maplibregl.Map): void {
  if (!map.getSource(NASA_CONTEXT_SOURCE)) map.addSource(NASA_CONTEXT_SOURCE, {
    type: "raster",
    tileSize: 256,
    maxzoom: 8,
    tiles: [
      "https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/BlueMarble_ShadedRelief_Bathymetry/default/GoogleMapsCompatible_Level8/{z}/{y}/{x}.jpeg",
    ],
    attribution: '<a href="https://earthdata.nasa.gov/centers/gibs">NASA GIBS · Blue Marble / MODIS</a>',
  });
  if (!map.getLayer("nasa-imagery")) map.addLayer(
    {
      id: "nasa-imagery",
      type: "raster",
      source: NASA_CONTEXT_SOURCE,
      paint: { "raster-saturation": -0.3, "raster-brightness-max": 0.8 },
    },
    "prospectivity-screened",
  );
}
