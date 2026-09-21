import type * as maplibregl from "maplibre-gl";
import type { FillLayerSpecification } from "maplibre-gl";
import type { FeatureCollection, Polygon } from "geojson";
import type { CellProperties } from "@/lib/api/heatmap";
import { prospectivityLayers } from "./prospectivity-layers";
import { registerMaskPattern } from "./register-mask-pattern";
import { MAP_IDS, framingPadding, type LngLatExtent } from "./sites";

/** NASA GIBS context source. Geographic context only, never model input. */
export const NASA_CONTEXT_SOURCE = "nasa-context";

/** Frames the view and adds the prospectivity surface, then the NASA context
 * imagery beneath it. Runs once, on `load`. Mines and targets are DOM markers
 * (components/explorer/map-markers.ts), added by the canvas itself. */
export function installMaplibreLayers(
  map: maplibregl.Map,
  { surface, extent }: { surface: FeatureCollection<Polygon, CellProperties>; extent: LngLatExtent },
): void {
  // Fit for this viewport; never treat camera bounds as scope.
  if (!map.getSource(MAP_IDS.surface)) {
    map.fitBounds(extent, { duration: 0, padding: framingPadding(map.getContainer().clientWidth, "initial") });
  }
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
