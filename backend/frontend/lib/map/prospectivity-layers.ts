import type { FillLayerSpecification } from "mapbox-gl";
import specification from "@/public/styles/prospectivity.layers.json";

/** The committed vector-tile style is also used by the mock GeoJSON source.
 * GeoJSON has no source-layer; keeping it would silently prevent rendering.
 */
export function prospectivityLayers(sourceType: "geojson" | "vector"): FillLayerSpecification[] {
  return specification.map((layer) => {
    const copy = structuredClone(layer) as FillLayerSpecification;
    if (sourceType === "geojson") delete copy["source-layer"];
    return copy;
  });
}
