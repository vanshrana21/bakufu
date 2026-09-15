"use client";
import { useEffect, useRef, useState } from "react";
import { Satellite } from "lucide-react";
import * as maplibregl from "maplibre-gl";
import type { GeoJSONSource } from "maplibre-gl";
import { NASA_CONTEXT_SOURCE, addNasaContext, installMaplibreLayers } from "@/lib/map/maplibre-layers";
import {
  MAP_IDS, SITE_LABEL_MARKER, framingPadding, prefersReducedMotion, renderedCounts, sameCounts,
  siteExtent, siteFeatures, siteLabelElement,
} from "@/lib/map/sites";
import type { MapCanvasProps } from "./map-canvas";
import { MapFitControl } from "./map-fit-control";
import { MapLegend } from "./map-legend";

const CLICKABLE_LAYERS = [MAP_IDS.wasteLayer, MAP_IDS.diagnosticLayer];

/** Mapbox v3 requires a token even for local data. This open renderer is used
 * ONLY when no token is configured; it consumes the same fixtures + layer spec.
 * NASA Blue Marble is geographic context, not Sentinel imagery or ML evidence.
 */
export default function TokenlessMapCanvas(props: MapCanvasProps) {
  const container = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const markerRef = useRef<maplibregl.Marker | null>(null);
  const latest = useRef(props);
  const [ready, setReady] = useState(false);
  const [failure, setFailure] = useState<string | null>(null);
  const [imagery, setImagery] = useState(false);
  const [rendered, setRendered] = useState({ cells: 0, excluded: 0, waste: 0 });

  useEffect(() => {
    latest.current = props;
  }, [props]);

  // Map lifecycle: created once, torn down on unmount.
  useEffect(() => {
    if (!container.current) return;
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
      setFailure("WebGL is unavailable. Use the screening locations below; scores remain accessible.");
      return;
    }
    mapRef.current = map;
    map.addControl(new maplibregl.NavigationControl({ showCompass: true }), "top-right");
    map.addControl(new maplibregl.ScaleControl({ unit: "metric" }), "bottom-left");
    map.addControl(new maplibregl.AttributionControl({ compact: true }), "bottom-right");
    const observer = new ResizeObserver(() => map.resize());
    observer.observe(container.current);

    const onLoad = () => {
      installMaplibreLayers(map, latest.current);
      setReady(true); // Local data is ready independently of the basemap network.
      addNasaContext(map);
    };
    const onRender = () => {
      if (!map.getLayer(MAP_IDS.wasteLayer)) return;
      const next = renderedCounts(
        (layers) => map.queryRenderedFeatures({ layers }),
        (id) => Boolean(map.getLayer(id)),
      );
      setRendered((old) => (sameCounts(old, next) ? old : next));
    };
    const onSourceData = (event: maplibregl.MapSourceDataEvent) => {
      if (event.sourceId === NASA_CONTEXT_SOURCE && event.tile?.state === "loaded") {
        setImagery(true);
        setFailure(null);
      }
    };
    const onError = (event: maplibregl.ErrorEvent) => {
      if ("sourceId" in event && event.sourceId === NASA_CONTEXT_SOURCE) {
        setFailure("Satellite context unavailable. Synthetic screening layers remain usable.");
      } else {
        setFailure("A map resource could not load. Use the location list to inspect the same evidence.");
      }
    };
    const onClick = (event: maplibregl.MapMouseEvent) => {
      if (!map.getLayer(MAP_IDS.wasteLayer)) return;
      const features = map.queryRenderedFeatures(event.point, { layers: CLICKABLE_LAYERS });
      const id: unknown = features[0]?.properties.id;
      if (typeof id === "string") latest.current.onSelect(id);
      else latest.current.onUnmappedClick();
    };
    const onEnter = () => {
      map.getCanvas().style.cursor = "pointer";
    };
    const onLeave = () => {
      map.getCanvas().style.cursor = "";
    };

    map.on("load", onLoad);
    map.on("render", onRender);
    map.on("sourcedata", onSourceData);
    map.on("error", onError);
    map.on("click", onClick);
    for (const layer of CLICKABLE_LAYERS) {
      map.on("mouseenter", layer, onEnter);
      map.on("mouseleave", layer, onLeave);
    }
    return () => {
      observer.disconnect();
      markerRef.current?.remove();
      markerRef.current = null;
      map.off("load", onLoad);
      map.off("render", onRender);
      map.off("sourcedata", onSourceData);
      map.off("error", onError);
      map.off("click", onClick);
      for (const layer of CLICKABLE_LAYERS) {
        map.off("mouseenter", layer, onEnter);
        map.off("mouseleave", layer, onLeave);
      }
      map.remove();
      mapRef.current = null;
    };
  }, []);

  // Data and selection: new source contents, the selection highlight and the
  // name tag. The camera is left where the user put it.
  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map) return;
    (map.getSource(MAP_IDS.sites) as GeoJSONSource).setData(siteFeatures(props.sites));
    (map.getSource(MAP_IDS.surface) as GeoJSONSource).setData(props.surface);
    map.removeFeatureState({ source: MAP_IDS.sites });
    markerRef.current?.remove();
    markerRef.current = null;
    const site = props.sites.find((s) => s.id === props.selectedSiteId);
    if (site?.location) {
      map.setFeatureState({ source: MAP_IDS.sites, id: site.id }, { selected: true });
      markerRef.current = new maplibregl.Marker({ element: siteLabelElement(site.name), ...SITE_LABEL_MARKER })
        .setLngLat([site.location.longitude, site.location.latitude])
        .addTo(map);
    }
  }, [props.sites, props.activeMask, props.surface, props.selectedSiteId, ready]);

  const refit = () => {
    const map = mapRef.current;
    const extent = siteExtent(props.sites, { inScopeOnly: true });
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
      data-rendered-waste={rendered.waste}
    >
      <div
        ref={container}
        className="absolute inset-0"
        aria-label="Sausar geographic context with synthetic prospectivity and waste markers"
      />
      <div className="map-token-notice" role="status">
        <Satellite size={14} />
        <span>
          {failure ??
            (imagery
              ? "NASA Blue Marble · low-resolution geographic context, not model input"
              : "Loading NASA context · synthetic screening layers")}
          <span className="map-context-secondary">
            <strong>Map token required</strong> for Mapbox satellite · open
            renderer active
          </span>
        </span>
      </div>
      {!ready && (
        <p role="status" className="absolute inset-x-5 top-28 text-sm text-[var(--canvas-ink)]">
          {failure ?? "Loading local screening layers…"}
        </p>
      )}
      <MapFitControl disabled={!ready || siteExtent(props.sites, { inScopeOnly: true }) === null} onFit={refit} />
      <MapLegend />
    </div>
  );
}
