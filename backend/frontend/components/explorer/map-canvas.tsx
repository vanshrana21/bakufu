"use client";

import { useEffect, useRef, useState } from "react";
import dynamic from "next/dynamic";
import { MapLegend } from "./map-legend";
import "./map-presentation.css";
import mapboxgl, { type GeoJSONSource, type MapMouseEvent } from "mapbox-gl";
import type { FeatureCollection, Polygon } from "geojson";
import { LocateFixed, Satellite } from "lucide-react";
import type { MaskMode, MineLocation, Target } from "@/lib/contracts";
import type { Selection } from "@/stores/explorer-store";
import type { CellProperties } from "@/fixtures/prospectivity-surface";
import { registerMaskPattern } from "@/lib/map/register-mask-pattern";
import { prospectivityLayers } from "@/lib/map/prospectivity-layers";
import { renderMarkers, type MarkerConstructor } from "./map-markers";

export interface MapCanvasProps {
  /** The ten operating mines, at their cited coordinates. */
  mines: readonly MineLocation[];
  /** The model's ranked greenfield targets. */
  targets: readonly Target[];
  activeMask: MaskMode;
  selected: Selection | null;
  onSelect: (selection: Selection) => void;
  onUnmappedClick: () => void;
  /** Prospectivity cells: the /prospectivity/heatmap lattice as polygons. */
  surface: FeatureCollection<Polygon, CellProperties>;
}

const publicToken = (
  process.env.NEXT_PUBLIC_MAPBOX_TOKEN ??
  process.env.NEXT_PUBLIC_MAPBOX_ACCESS_TOKEN ??
  ""
).trim();

/** Every marker position, for camera fitting only — never a scope boundary. */
export function markerPoints(props: MapCanvasProps): [number, number][] {
  return [
    ...props.mines.map((mine): [number, number] => [mine.location.longitude, mine.location.latitude]),
    ...props.targets.map((target): [number, number] => [target.location.longitude, target.location.latitude]),
  ];
}

/** Fallback plot while the GL map is still coming up: the belt bbox mapped to
 * the panel, so the coordinates are readable even with no renderer. */
function projectedPosition(longitude: number, latitude: number) {
  const left = 8 + ((longitude - 79.0) / (80.6 - 79.0)) * 84;
  const top = 88 - ((latitude - 21.3) / (22.1 - 21.3)) * 72;
  return {
    left: `${Math.max(6, Math.min(94, left))}%`,
    top: `${Math.max(10, Math.min(90, top))}%`,
  };
}

const TokenlessMap = dynamic(() => import("./tokenless-map-canvas"), { ssr: false });

export default function MapCanvas(props: MapCanvasProps) {
  return publicToken ? <MapboxCanvas {...props} /> : <TokenlessMap {...props} />;
}

function MapboxCanvas(props: MapCanvasProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<mapboxgl.Map | null>(null);
  const disposeMarkers = useRef<(() => void) | null>(null);
  const latest = useRef(props);
  const [styleRevision, setStyleRevision] = useState(0);
  const [ready, setReady] = useState(false);
  const [failure, setFailure] = useState<string | null>(null);
  const [rendered, setRendered] = useState({ cells: 0, excluded: 0 });

  useEffect(() => {
    latest.current = props;
  }, [props]);

  useEffect(() => {
    if (!containerRef.current) return;
    if (!mapboxgl.supported()) {
      setFailure("WebGL is unavailable in this browser. Use the lists beside the map.");
      return;
    }
    let map: mapboxgl.Map;
    try {
      map = new mapboxgl.Map({
        container: containerRef.current,
        accessToken: publicToken || undefined,
        style: publicToken
          ? "mapbox://styles/mapbox/satellite-streets-v12"
          : {
              version: 8,
              sources: {},
              layers: [{ id: "paper-terrain", type: "background", paint: { "background-color": "#150C0C" } }],
            },
        center: [79.65, 21.7],
        zoom: 9.4,
        // This camera is navigation only - not a Sausar validation boundary.
        attributionControl: true,
        preserveDrawingBuffer: true,
      });
    } catch {
      setFailure("The map could not initialize. Use the lists beside the map.");
      return;
    }
    mapRef.current = map;
    map.addControl(new mapboxgl.NavigationControl({ showCompass: false }), "top-right");
    map.addControl(new mapboxgl.ScaleControl({ unit: "metric" }), "bottom-left");
    const observer = new ResizeObserver(() => map.resize());
    observer.observe(containerRef.current);
    const timeout = setTimeout(
      () => setFailure("Satellite tiles are taking too long to load. The lists remain available."),
      15000,
    );

    const installLayers = () => {
      if (!map.getSource("prediction-cells")) {
        const bounds = new mapboxgl.LngLatBounds();
        for (const [longitude, latitude] of markerPoints(latest.current))
          bounds.extend([longitude, latitude]);
        if (!bounds.isEmpty())
          map.fitBounds(bounds, {
            duration: 0,
            padding: { top: 80, bottom: map.getContainer().clientWidth < 600 ? 150 : 42, left: 45, right: 45 },
          });
      }
      registerMaskPattern(map);
      if (!map.getSource("prediction-cells"))
        map.addSource("prediction-cells", { type: "geojson", data: latest.current.surface });
      for (const layer of prospectivityLayers("geojson"))
        if (!map.getLayer(layer.id)) map.addLayer(layer);
      if (!map.getLayer("prediction-outlines"))
        map.addLayer({
          id: "prediction-outlines",
          type: "line",
          source: "prediction-cells",
          paint: { "line-color": "#EACEAA", "line-width": 1, "line-opacity": 0.65 },
        });
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
        "Some map resources could not load. Check the public token, allowed URLs and network. The lists remain available.",
      );
    };
    const onIdle = () => {
      const count = (layers: string[]) =>
        new Set(
          map
            .queryRenderedFeatures({ layers: layers.filter((id) => map.getLayer(id)) })
            .map((f) => f.properties?.id),
        ).size;
      const next = {
        cells: count(["prospectivity-screened", "prospectivity-excluded"]),
        excluded: count(["prospectivity-excluded"]),
      };
      setRendered((previous) =>
        previous.cells === next.cells && previous.excluded === next.excluded ? previous : next,
      );
    };
    // Markers stop their own clicks, so anything reaching the map is empty
    // ground. Scoring an arbitrary coordinate is a backend decision, never an
    // inference from the camera extent.
    const onClick = (_event: MapMouseEvent) => latest.current.onUnmappedClick();

    map.on("style.load", installLayers);
    map.on("load", onLoad);
    map.on("error", onError);
    map.on("idle", onIdle);
    map.on("click", onClick);
    return () => {
      clearTimeout(timeout);
      observer.disconnect();
      disposeMarkers.current?.();
      disposeMarkers.current = null;
      map.off("style.load", installLayers);
      map.off("load", onLoad);
      map.off("error", onError);
      map.off("idle", onIdle);
      map.off("click", onClick);
      map.remove();
      mapRef.current = null;
    };
  }, []);

  useEffect(() => {
    const surface = mapRef.current?.getSource("prediction-cells") as GeoJSONSource | undefined;
    surface?.setData(props.surface);
  }, [props.activeMask, props.surface, styleRevision]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    disposeMarkers.current?.();
    disposeMarkers.current = renderMarkers(
      map,
      mapboxgl.Marker as unknown as MarkerConstructor,
      { mines: props.mines, targets: props.targets, selected: props.selected, onSelect: props.onSelect },
    );
    // The camera is deliberately preserved when a selection or mask changes.
  }, [props.mines, props.targets, props.selected, props.onSelect, styleRevision]);

  return (
    <div
      className="map-presentation absolute inset-0"
      data-testid="map-render-state"
      data-ready={ready}
      data-rendered-cells={rendered.cells}
      data-rendered-excluded={rendered.excluded}
      data-rendered-markers={props.mines.length + props.targets.length}
    >
      <div
        ref={containerRef}
        className="absolute inset-0"
        aria-label="Satellite map with MOIL mines and model targets"
      />
      {!ready && (
        <div className="absolute inset-0 overflow-hidden bg-[var(--canvas)] text-[var(--canvas-ink)]">
          <div
            className="absolute left-[8%] right-[8%] top-[12%] bottom-[12%] border border-[var(--map-out-of-scope)]"
            aria-hidden="true"
          />
          {[
            ...props.mines.map((mine) => ({
              kind: "mine" as const, id: mine.name, label: mine.name, location: mine.location,
            })),
            ...props.targets.map((target) => ({
              kind: "target" as const, id: target.id, label: target.id, location: target.location,
            })),
          ].map((item) => {
            const position = projectedPosition(item.location.longitude, item.location.latitude);
            const active = props.selected?.kind === item.kind && props.selected.id === item.id;
            return (
              <button
                key={`${item.kind}:${item.id}`}
                type="button"
                onClick={() => props.onSelect({ kind: item.kind, id: item.id })}
                aria-label={`Inspect ${item.label}`}
                aria-pressed={active}
                className={`map-marker map-marker--${item.kind} absolute z-10 -translate-x-1/2 -translate-y-1/2`}
                data-selected={active}
                style={position}
              >
                <span className="map-marker-tag">{item.label}</span>
              </button>
            );
          })}
          <div
            role="status"
            className="pointer-events-none absolute left-4 right-4 top-[72px] text-xs leading-5 text-[var(--canvas-muted)]"
          >
            <p className="flex items-center gap-2">
              <Satellite size={14} />
              <strong className="font-medium text-[var(--canvas-ink)]">
                {failure ? "Map rendering unavailable" : "Loading map layers"}
              </strong>
              <span className="hidden sm:inline">· Coordinate plot of mines and targets</span>
            </p>
            <p className="sr-only">{failure ?? "The selection workflow remains available."}</p>
          </div>
        </div>
      )}
      {ready && failure && (
        <div
          role="status"
          className="absolute left-4 right-16 top-16 rounded bg-[var(--canvas-ink)] px-3 py-2 text-xs text-foreground"
        >
          {failure}
        </div>
      )}
      {!publicToken && (
        <div className="map-token-notice">
          <Satellite size={13} />
          <span>
            <strong>Map token required</strong> for satellite imagery · model surface on a plain
            basemap
          </span>
        </div>
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
          const bounds = new mapboxgl.LngLatBounds();
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
