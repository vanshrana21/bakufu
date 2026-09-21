"use client";
import { useEffect, useRef, useState } from "react";
import { Satellite } from "lucide-react";
import * as maplibregl from "maplibre-gl";
import type { GeoJSONSource } from "maplibre-gl";
import { NASA_CONTEXT_SOURCE, addNasaContext, installMaplibreLayers } from "@/lib/map/maplibre-layers";
import {
  MAP_IDS, framingPadding, initialExtent, markerPoints, pointsExtent, prefersReducedMotion, renderedCounts, sameCounts,
} from "@/lib/map/sites";
import type { MapCanvasProps } from "./map-canvas";
import { renderMarkers, type MarkerConstructor } from "./map-markers";
import { MapFitControl } from "./map-fit-control";
import { MapLegend } from "./map-legend";

/** Mapbox v3 requires a token even for local data. This open renderer is used
 * ONLY when no token is configured; it draws the same layer spec and the same
 * markers. NASA Blue Marble is geographic context, not Sentinel imagery or
 * model evidence.
 */
export default function TokenlessMapCanvas(props: MapCanvasProps) {
  const container = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const latest = useRef(props);
  const [ready, setReady] = useState(false);
  const [failure, setFailure] = useState<string | null>(null);
  const [imagery, setImagery] = useState(false);
  const [rendered, setRendered] = useState({ cells: 0, excluded: 0 });

  useEffect(() => {
    latest.current = props;
  }, [props]);

  // Map lifecycle: created once, torn down on unmount.
  useEffect(() => {
    if (!container.current) return;
    let active = true;
    const guard = (callback: () => void) => { if (active) callback(); };
    let map: maplibregl.Map;
    try {
      map = new maplibregl.Map({
        container: container.current,
        center: [79.65, 21.7],
        zoom: 9.4,
        canvasContextAttributes: { preserveDrawingBuffer: true },
        style: { version: 8, sources: {}, layers: [{ id: "plain-basemap", type: "background", paint: { "background-color": "#150C0C" } }] },
        attributionControl: false,
      });
    } catch {
      guard(() => setFailure("WebGL is unavailable. Use the lists beside the map; scores remain accessible."));
      return;
    }
    mapRef.current = map;
    map.addControl(new maplibregl.NavigationControl({ showCompass: true }), "top-right");
    map.addControl(new maplibregl.ScaleControl({ unit: "metric" }), "bottom-left");
    map.addControl(new maplibregl.AttributionControl({ compact: true }), "bottom-right");
    const observer = new ResizeObserver(() => map.resize());
    observer.observe(container.current);

    const onLoad = () => {
      try {
        const { mines, targets, surface } = latest.current;
        installMaplibreLayers(map, { surface, extent: initialExtent(markerPoints(mines, targets)) });
        guard(() => setReady(true)); // Local data is ready independently of the basemap network.
        addNasaContext(map);
      } catch {
        guard(() => setFailure("Map layers could not be installed. Use the lists beside the map."));
      }
    };
    // Counted when the map settles, not on every frame: queryRenderedFeatures
    // on each render turns a pan into continuous query work for a number that
    // only matters once drawing has stopped.
    const onIdle = () => {
      if (!map.getLayer("prospectivity-screened")) return;
      const next = renderedCounts(
        (layers) => map.queryRenderedFeatures({ layers }),
        (id) => Boolean(map.getLayer(id)),
      );
      setRendered((old) => (sameCounts(old, next) ? old : next));
    };
    const onSourceData = (event: maplibregl.MapSourceDataEvent) => {
      if (event.sourceId === NASA_CONTEXT_SOURCE && event.tile?.state === "loaded") {
        guard(() => { setImagery(true); setFailure(null); });
      }
    };
    const onError = (event: maplibregl.ErrorEvent) => {
      if ("sourceId" in event && event.sourceId === NASA_CONTEXT_SOURCE) {
        guard(() => setFailure("Satellite context unavailable. The model surface remains usable."));
      } else {
        guard(() => setFailure("A map resource could not load. Use the lists beside the map to inspect the same evidence."));
      }
    };
    // Markers stop their own clicks, so anything arriving here is empty ground.
    const onClick = (event: maplibregl.MapMouseEvent) =>
      latest.current.onUnmappedClick({
        latitude: event.lngLat.lat,
        longitude: event.lngLat.lng,
      });

    map.on("load", onLoad);
    map.on("idle", onIdle);
    map.on("sourcedata", onSourceData);
    map.on("error", onError);
    map.on("click", onClick);
    return () => {
      active = false;
      observer.disconnect();
      map.off("load", onLoad);
      map.off("idle", onIdle);
      map.off("sourcedata", onSourceData);
      map.off("error", onError);
      map.off("click", onClick);
      map.remove();
      mapRef.current = null;
    };
  }, []);

  // Data: new surface contents. The camera is left where the user put it.
  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map) return;
    try {
      (map.getSource(MAP_IDS.surface) as GeoJSONSource | undefined)?.setData(props.surface);
    } catch {
      setFailure("Map data could not be updated. Use the lists beside the map.");
    }
  }, [props.surface, ready]);

  // Markers: redrawn when the mines, the targets or the selection change.
  const { mines, targets, selected } = props;
  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map) return;
    return renderMarkers(map, maplibregl.Marker as unknown as MarkerConstructor, {
      mines,
      targets,
      selected,
      onSelect: (selection) => latest.current.onSelect(selection),
    });
  }, [mines, targets, selected, ready]);

  const extent = pointsExtent(markerPoints(mines, targets));
  const refit = () => {
    const map = mapRef.current;
    if (!map || !extent) return;
    map.fitBounds(extent, {
      duration: prefersReducedMotion() ? 0 : 500,
      padding: framingPadding(map.getContainer().clientWidth, "refit"),
    });
  };

  return (
    <div
      className="map-presentation absolute inset-0"
      data-testid="map-render-state"
      data-renderer="maplibre"
      data-ready={ready}
      data-imagery={imagery}
      data-rendered-cells={rendered.cells}
      data-rendered-excluded={rendered.excluded}
      data-rendered-markers={mines.length + targets.length}
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
            <strong>Map token required</strong> for Mapbox satellite · open
            renderer active
          </span>
        </span>
      </div>
      {!ready && (
        <p role="status" className="absolute inset-x-5 top-28 text-sm text-[var(--canvas-ink)]">
          {failure ?? "Loading the map…"}
        </p>
      )}
      <MapFitControl disabled={!ready || extent === null} onFit={refit} />
      <MapLegend origin={props.surfaceOrigin} />
    </div>
  );
}
