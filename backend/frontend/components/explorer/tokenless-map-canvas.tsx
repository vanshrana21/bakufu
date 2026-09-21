"use client";
import { useEffect, useRef, useState } from "react";
import { LocateFixed, Satellite } from "lucide-react";
import * as maplibregl from "maplibre-gl";
import type { FillLayerSpecification, GeoJSONSource } from "maplibre-gl";
import { registerMaskPattern } from "@/lib/map/register-mask-pattern";
import { prospectivityLayers } from "@/lib/map/prospectivity-layers";
import { markerPoints, type MapCanvasProps } from "./map-canvas";
import { renderMarkers, type MarkerConstructor } from "./map-markers";
import { MapLegend } from "./map-legend";

const SURFACE = "prediction-cells";

/** Mapbox v3 requires a token even for local data. This open renderer is used
 * ONLY when no token is configured; it consumes the same layer spec and the
 * same markers. NASA Blue Marble is geographic context, not Sentinel imagery
 * or model evidence.
 */
export default function TokenlessMapCanvas(props: MapCanvasProps) {
  const container = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const disposeMarkers = useRef<(() => void) | null>(null);
  const latest = useRef(props);
  const [ready, setReady] = useState(false);
  const [failure, setFailure] = useState<string | null>(null);
  const [imagery, setImagery] = useState(false);
  const [rendered, setRendered] = useState({ cells: 0, excluded: 0 });
  useEffect(() => {
    latest.current = props;
  }, [props]);
  useEffect(() => {
    if (!container.current) return;
    let map: maplibregl.Map;
    try {
      map = new maplibregl.Map({
        container: container.current,
        center: [79.65, 21.7],
        zoom: 9.4,
        canvasContextAttributes: { preserveDrawingBuffer: true },
        style: {
          version: 8,
          sources: {},
          layers: [{ id: "plain-basemap", type: "background", paint: { "background-color": "#150C0C" } }],
        },
        attributionControl: false,
      });
    } catch {
      setFailure("WebGL is unavailable. Use the lists beside the map; scores remain accessible.");
      return;
    }
    mapRef.current = map;
    map.addControl(new maplibregl.NavigationControl({ showCompass: true }), "top-right");
    map.addControl(new maplibregl.ScaleControl({ unit: "metric" }), "bottom-left");
    map.addControl(new maplibregl.AttributionControl({ compact: true }), "bottom-right");
    const observer = new ResizeObserver(() => map.resize());
    observer.observe(container.current);
    const install = () => {
      // Fit the markers for this viewport; never treat camera bounds as scope.
      const bounds = new maplibregl.LngLatBounds();
      for (const point of markerPoints(latest.current)) bounds.extend(point);
      if (!bounds.isEmpty())
        map.fitBounds(bounds, {
          duration: 0,
          padding: { top: 80, bottom: map.getContainer().clientWidth < 600 ? 150 : 42, left: 45, right: 45 },
        });
      registerMaskPattern(map);
      map.addSource(SURFACE, { type: "geojson", data: latest.current.surface });
      // Both engines implement these standard v8 fill expressions. Narrow cast
      // stays at the adapter boundary; no Mapbox-only paint properties are used.
      for (const layer of prospectivityLayers("geojson"))
        map.addLayer(layer as FillLayerSpecification);
      map.addLayer({
        id: "prediction-outlines",
        type: "line",
        source: SURFACE,
        paint: { "line-color": "#EACEAA", "line-width": 1, "line-opacity": 0.8 },
      });
      setReady(true); // Local data is ready independently of the basemap network.
      map.addSource("nasa-context", {
        type: "raster",
        tileSize: 256,
        maxzoom: 8,
        tiles: [
          "https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/BlueMarble_ShadedRelief_Bathymetry/default/GoogleMapsCompatible_Level8/{z}/{y}/{x}.jpeg",
        ],
        attribution:
          '<a href="https://earthdata.nasa.gov/centers/gibs">NASA GIBS · Blue Marble / MODIS</a>',
      });
      map.addLayer(
        {
          id: "nasa-imagery",
          type: "raster",
          source: "nasa-context",
          paint: { "raster-saturation": -0.3, "raster-brightness-max": 0.8 },
        },
        "prospectivity-screened",
      );
    };
    const counts = () => {
      if (!map.getLayer("prospectivity-screened")) return;
      const count = (layers: string[]) =>
        new Set(map.queryRenderedFeatures({ layers }).map((f) => f.properties.id)).size;
      const next = {
        cells: count(["prospectivity-screened", "prospectivity-excluded"]),
        excluded: count(["prospectivity-excluded"]),
      };
      setRendered((old) => (old.cells === next.cells && old.excluded === next.excluded ? old : next));
    };
    const dataLoaded = (event: maplibregl.MapSourceDataEvent) => {
      if (event.sourceId === "nasa-context" && event.tile?.state === "loaded") {
        setImagery(true);
        setFailure(null);
      }
    };
    const onError = (event: maplibregl.ErrorEvent) => {
      if ("sourceId" in event && event.sourceId === "nasa-context")
        setFailure("Satellite context unavailable. The model surface remains usable.");
      else setFailure("A map resource could not load. Use the lists to inspect the same evidence.");
    };
    // Markers stop their own clicks, so anything arriving here is empty ground.
    const click = () => latest.current.onUnmappedClick();
    map.on("load", install);
    map.on("render", counts);
    map.on("sourcedata", dataLoaded);
    map.on("error", onError);
    map.on("click", click);
    return () => {
      observer.disconnect();
      disposeMarkers.current?.();
      disposeMarkers.current = null;
      map.off("load", install);
      map.off("render", counts);
      map.off("sourcedata", dataLoaded);
      map.off("error", onError);
      map.off("click", click);
      map.remove();
      mapRef.current = null;
    };
  }, []);
  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map) return;
    (map.getSource(SURFACE) as GeoJSONSource).setData(props.surface);
  }, [props.activeMask, props.surface, ready]);
  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map) return;
    disposeMarkers.current?.();
    disposeMarkers.current = renderMarkers(
      map,
      maplibregl.Marker as unknown as MarkerConstructor,
      { mines: props.mines, targets: props.targets, selected: props.selected, onSelect: props.onSelect },
    );
  }, [props.mines, props.targets, props.selected, props.onSelect, ready]);
  return (
    <div
      className="map-presentation absolute inset-0"
      data-testid="map-render-state"
      data-renderer="maplibre"
      data-ready={ready}
      data-imagery={imagery}
      data-rendered-cells={rendered.cells}
      data-rendered-excluded={rendered.excluded}
      data-rendered-markers={props.mines.length + props.targets.length}
    >
      <div
        ref={container}
        className="absolute inset-0"
        aria-label="Sausar geographic context with the model surface, MOIL mines and model targets"
      />
      <div className="map-token-notice" role="status">
        <Satellite size={14} />
        <span>
          {failure ??
            (imagery
              ? "NASA Blue Marble · low-resolution geographic context, not model input"
              : "Loading NASA context · model surface active")}
          <span className="map-context-secondary">
            <strong>Map token required</strong> for Mapbox satellite · open renderer active
          </span>
        </span>
      </div>
      {!ready && (
        <p role="status" className="absolute inset-x-5 top-28 text-sm text-[var(--canvas-ink)]">
          {failure ?? "Loading model surface…"}
        </p>
      )}
      <button
        type="button"
        className="map-fit-control"
        aria-label="Fit mines and targets"
        title="Fit mines and targets"
        disabled={!ready || markerPoints(props).length === 0}
        onClick={() => {
          const map = mapRef.current;
          if (!map) return;
          const bounds = new maplibregl.LngLatBounds();
          for (const point of markerPoints(props)) bounds.extend(point);
          if (!bounds.isEmpty())
            map.fitBounds(bounds, {
              duration: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? 0 : 500,
              padding: { top: 90, bottom: map.getContainer().clientWidth < 600 ? 170 : 75, left: 45, right: 45 },
            });
        }}
      >
        <LocateFixed size={17} />
      </button>
      <MapLegend />
    </div>
  );
}
