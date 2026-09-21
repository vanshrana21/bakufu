"use client";

import dynamic from "next/dynamic";
import { Satellite } from "lucide-react";
import type { FeatureCollection, Polygon } from "geojson";
import type { MaskMode, MineLocation, Target } from "@/lib/contracts";
import type { CellProperties } from "@/lib/api/heatmap";
import type { Selection } from "@/stores/explorer-store";
import { MAPBOX_PUBLIC_TOKEN, useMapboxEngine } from "@/hooks/use-mapbox-engine";
import { useMapboxMarkers } from "@/hooks/use-mapbox-markers";
import { useMapboxSync } from "@/hooks/use-mapbox-sync";
import { framingPadding, initialExtent, markerPoints, pointsExtent, prefersReducedMotion } from "@/lib/map/sites";
import { MapFallbackPlot } from "./map-fallback-plot";
import { MapFitControl } from "./map-fit-control";
import { MapLegend } from "./map-legend";
import "./map-presentation.css";

export interface MapCanvasProps {
  mines: readonly MineLocation[];
  targets: readonly Target[];
  activeMask: MaskMode;
  selected: Selection | null;
  onSelect: (selection: Selection) => void;
  /** A click on empty ground: arbitrary coordinates are not scored from here. */
  onUnmappedClick: () => void;
  /** Prospectivity cells: the live /prospectivity/heatmap lattice as polygons. */
  surface: FeatureCollection<Polygon, CellProperties>;
  /** Whether the cells are served model output or nothing at all (no backend). */
  surfaceOrigin: "live" | "fixture";
}

const TokenlessMap = dynamic(() => import("./tokenless-map-canvas"), {
  ssr: false,
});

/** Mapbox satellite when a public token is configured, the open MapLibre
 * renderer otherwise. Both draw the same layers and the same markers. */
export default function MapCanvas(props: MapCanvasProps) {
  return MAPBOX_PUBLIC_TOKEN ? <MapboxCanvas {...props} /> : <TokenlessMap {...props} />;
}

/** Wiring only: the engine owns the map, the sync hook the surface, the
 * markers hook the mines, targets and clicks. Nothing here holds map state. */
function MapboxCanvas({ mines, targets, surface, surfaceOrigin, selected, onSelect, onUnmappedClick }: MapCanvasProps) {
  const engine = useMapboxEngine();
  const points = markerPoints(mines, targets);
  const extent = pointsExtent(points);
  const { rendered, failure: layerFailure } = useMapboxSync(engine, { surface, extent: initialExtent(points) });
  useMapboxMarkers(engine.map, { mines, targets, selected, onSelect, onUnmappedClick });

  const refit = () => {
    const map = engine.map;
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
      data-ready={engine.ready}
      data-rendered-cells={rendered.cells}
      data-rendered-excluded={rendered.excluded}
      data-rendered-markers={points.length}
    >
      <div ref={engine.containerRef} className="absolute inset-0" aria-label="Satellite map with the model surface, MOIL mines and model targets" />
      {!engine.ready && (
        <MapFallbackPlot mines={mines} targets={targets} selected={selected} onSelect={onSelect} failure={engine.failure} />
      )}
      {engine.ready && (engine.failure || layerFailure) && (
        <div role="status" className="absolute left-4 right-16 top-16 rounded bg-[var(--canvas-ink)] px-3 py-2 text-xs text-foreground">
          {layerFailure ?? engine.failure}
        </div>
      )}
      <MapFitControl disabled={!engine.ready || extent === null} onFit={refit} />
      <MapLegend origin={surfaceOrigin} />
    </div>
  );
}
