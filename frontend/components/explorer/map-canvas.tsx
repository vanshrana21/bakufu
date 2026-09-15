"use client";

import { useEffect, useRef, useState } from "react";
import dynamic from "next/dynamic";
import { MapLegend } from "./map-legend";
import "./map-presentation.css";
import mapboxgl, { type GeoJSONSource, type MapMouseEvent } from "mapbox-gl";
import type { FeatureCollection, Polygon } from "geojson";
import { Satellite } from "lucide-react";
import type { SiteFixture } from "@/fixtures/predictions";
import type { MaskMode } from "@/lib/contracts";
import type { CellProperties } from "@/fixtures/prospectivity-surface";
import { installMapboxLayers } from "@/lib/map/mapbox-layers";
import {
  MAP_IDS, SITE_LABEL_MARKER, framingPadding, prefersReducedMotion, renderedCounts, sameCounts,
  siteExtent, siteFeatures, siteLabelElement,
} from "@/lib/map/sites";
import { MapFallbackPlot } from "./map-fallback-plot";
import { MapFitControl } from "./map-fit-control";

export interface MapCanvasProps {
  sites: readonly SiteFixture[];
  activeMask: MaskMode;
  selectedSiteId: string | null;
  onSelect: (siteId: string) => void;
  onUnmappedClick: () => void;
  /** Prospectivity cells. Fixture blobs, or the live /prospectivity/heatmap
   * lattice converted to polygons — the layer spec is identical for both. */
  surface: FeatureCollection<Polygon, CellProperties>;
}

const publicToken = (
  process.env.NEXT_PUBLIC_MAPBOX_TOKEN ??
  process.env.NEXT_PUBLIC_MAPBOX_ACCESS_TOKEN ??
  ""
).trim();

const CLICKABLE_LAYERS = [MAP_IDS.diagnosticLayer, MAP_IDS.wasteLayer];

const TokenlessMap = dynamic(() => import("./tokenless-map-canvas"), {
  ssr: false,
});

/** Mapbox satellite when a public token is configured, the open MapLibre
 * renderer otherwise. Both draw the same layers from the same helpers. */
export default function MapCanvas(props: MapCanvasProps) {
  return publicToken ? <MapboxCanvas {...props} /> : <TokenlessMap {...props} />;
}

function MapboxCanvas(props: MapCanvasProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<mapboxgl.Map | null>(null);
  const markerRef = useRef<mapboxgl.Marker | null>(null);
  const latest = useRef(props);
  const previousSelection = useRef<string | null>(null);
  const [styleRevision, setStyleRevision] = useState(0);
  const [ready, setReady] = useState(false);
  const [failure, setFailure] = useState<string | null>(null);
  const [rendered, setRendered] = useState({ cells: 0, excluded: 0, waste: 0 });

  useEffect(() => {
    latest.current = props;
  }, [props]);

  // Map lifecycle: created once, torn down on unmount. Data changes go through
  // the effects below so the camera and WebGL context survive them.
  useEffect(() => {
    if (!containerRef.current) return;
    if (!mapboxgl.supported()) {
      setFailure("WebGL is unavailable in this browser. Use the site list below.");
      return;
    }
    let map: mapboxgl.Map;
    try {
      map = new mapboxgl.Map({
        container: containerRef.current,
        accessToken: publicToken || undefined,
        // Satellite imagery needs the user's public token. The local style still
        // renders and exercises all mock GeoJSON layers offline without one.
        style: publicToken
          ? "mapbox://styles/mapbox/satellite-streets-v12"
          : { version: 8, sources: {}, layers: [{ id: "paper-terrain", type: "background", paint: { "background-color": "#150C0C" } }] },
        center: [79.65, 21.7],
        zoom: 9.4,
        // This camera is navigation only—not a Sausar validation boundary.
        attributionControl: true,
        preserveDrawingBuffer: true,
      });
    } catch {
      setFailure("The map could not initialize. Use the site list below.");
      return;
    }
    mapRef.current = map;
    map.addControl(new mapboxgl.NavigationControl({ showCompass: false }), "top-right");
    map.addControl(new mapboxgl.ScaleControl({ unit: "metric" }), "bottom-left");
    const observer = new ResizeObserver(() => map.resize());
    observer.observe(containerRef.current);
    const timeout = setTimeout(
      () => setFailure("Satellite tiles are taking too long to load. The site list remains available."),
      15000,
    );

    const onStyleLoad = () => {
      installMapboxLayers(map, latest.current);
      setStyleRevision((n) => n + 1);
    };
    const onLoad = () => {
      clearTimeout(timeout);
      setReady(true);
      setFailure(null);
    };
    const onError = (event: mapboxgl.ErrorEvent) => {
      if (event.error.message.includes("access token")) setReady(false);
      setFailure(
        "Some map resources could not load. Check the public token, allowed URLs and network. The site list remains available.",
      );
    };
    const onIdle = () => {
      // Source updates settle asynchronously, so counts are read once idle.
      const next = renderedCounts(
        (layers) => map.queryRenderedFeatures({ layers }),
        (id) => Boolean(map.getLayer(id)),
      );
      setRendered((previous) => (sameCounts(previous, next) ? previous : next));
    };
    const onClick = (event: MapMouseEvent) => {
      const layers = CLICKABLE_LAYERS.filter((id) => map.getLayer(id));
      const feature = layers.length ? map.queryRenderedFeatures(event.point, { layers })[0] : undefined;
      const id: unknown = feature?.properties?.id;
      if (typeof id === "string") latest.current.onSelect(id);
      // SAUSAR SCOPE CHECK for arbitrary coordinates belongs in the backend
      // point-query response. Never treat the camera extent as validated scope.
      else latest.current.onUnmappedClick();
    };
    const onEnter = () => {
      map.getCanvas().style.cursor = "pointer";
    };
    const onLeave = () => {
      map.getCanvas().style.cursor = "";
    };

    map.on("style.load", onStyleLoad);
    map.on("load", onLoad);
    map.on("error", onError);
    map.on("idle", onIdle);
    map.on("click", onClick);
    for (const layer of CLICKABLE_LAYERS) {
      map.on("mouseenter", layer, onEnter);
      map.on("mouseleave", layer, onLeave);
    }
    return () => {
      clearTimeout(timeout);
      observer.disconnect();
      markerRef.current?.remove();
      markerRef.current = null;
      map.off("style.load", onStyleLoad);
      map.off("load", onLoad);
      map.off("error", onError);
      map.off("idle", onIdle);
      map.off("click", onClick);
      for (const layer of CLICKABLE_LAYERS) {
        map.off("mouseenter", layer, onEnter);
        map.off("mouseleave", layer, onLeave);
      }
      map.remove();
      mapRef.current = null;
    };
  }, []);

  // Data: replace source contents without recreating the map. The Ghost Reserve
  // filter is computed once in ExplorerWorkspace and passed to map and list alike.
  useEffect(() => {
    (mapRef.current?.getSource(MAP_IDS.sites) as GeoJSONSource | undefined)?.setData(siteFeatures(props.sites));
    (mapRef.current?.getSource(MAP_IDS.surface) as GeoJSONSource | undefined)?.setData(props.surface);
  }, [props.sites, props.activeMask, props.surface, styleRevision]);

  // Selection: highlight the chosen site and tag it with its name. The camera is
  // deliberately left where the user put it.
  useEffect(() => {
    const map = mapRef.current;
    if (!map?.getSource(MAP_IDS.sites)) return;
    if (previousSelection.current) {
      map.setFeatureState({ source: MAP_IDS.sites, id: previousSelection.current }, { selected: false });
    }
    if (props.selectedSiteId) {
      map.setFeatureState({ source: MAP_IDS.sites, id: props.selectedSiteId }, { selected: true });
    }
    previousSelection.current = props.selectedSiteId;
    markerRef.current?.remove();
    markerRef.current = null;
    const site = props.sites.find((candidate) => candidate.id === props.selectedSiteId);
    if (site?.location) {
      markerRef.current = new mapboxgl.Marker({ element: siteLabelElement(site.name), ...SITE_LABEL_MARKER })
        .setLngLat([site.location.longitude, site.location.latitude])
        .addTo(map);
    }
  }, [props.selectedSiteId, props.sites, styleRevision]);

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
      data-ready={ready}
      data-rendered-cells={rendered.cells}
      data-rendered-excluded={rendered.excluded}
      data-rendered-waste={rendered.waste}
    >
      <div ref={containerRef} className="absolute inset-0" aria-label="Satellite map with demonstration site markers" />
      {!ready && (
        <MapFallbackPlot sites={props.sites} selectedSiteId={props.selectedSiteId} onSelect={props.onSelect} failure={failure} />
      )}
      {ready && failure && (
        <div role="status" className="absolute left-4 right-16 top-16 rounded bg-[var(--canvas-ink)] px-3 py-2 text-xs text-foreground">
          {failure}
        </div>
      )}
      {!publicToken && (
        <div className="map-token-notice">
          <Satellite size={13} />
          <span>
            <strong>Map token required</strong> for satellite imagery · synthetic geometry on a plain basemap
          </span>
        </div>
      )}
      <MapFitControl disabled={!ready || siteExtent(props.sites, { inScopeOnly: true }) === null} onFit={refit} />
      <MapLegend />
    </div>
  );
}
