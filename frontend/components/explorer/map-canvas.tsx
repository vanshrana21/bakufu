"use client";

import dynamic from "next/dynamic";
import { Satellite } from "lucide-react";
import type { FeatureCollection, Polygon } from "geojson";
import type { SiteFixture } from "@/fixtures/predictions";
import type { MaskMode } from "@/lib/contracts";
import type { CellProperties } from "@/fixtures/prospectivity-surface";
import { MAPBOX_PUBLIC_TOKEN, useMapboxEngine } from "@/hooks/use-mapbox-engine";
import { useMapboxSelection } from "@/hooks/use-mapbox-selection";
import { useMapboxSync } from "@/hooks/use-mapbox-sync";
import { framingPadding, prefersReducedMotion, siteExtent } from "@/lib/map/sites";
import { MapFallbackPlot } from "./map-fallback-plot";
import { MapFitControl } from "./map-fit-control";
import { MapLegend } from "./map-legend";
import "./map-presentation.css";

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

const TokenlessMap = dynamic(() => import("./tokenless-map-canvas"), {
  ssr: false,
});

/** Mapbox satellite when a public token is configured, the open MapLibre
 * renderer otherwise. Both draw the same layers from the same helpers. */
export default function MapCanvas(props: MapCanvasProps) {
  return MAPBOX_PUBLIC_TOKEN ? <MapboxCanvas {...props} /> : <TokenlessMap {...props} />;
}

/** Wiring only: the engine owns the map, the sync hook what it draws, the
 * selection hook what a click means. Nothing here holds map state. */
function MapboxCanvas({ sites, surface, selectedSiteId, onSelect, onUnmappedClick }: MapCanvasProps) {
  const engine = useMapboxEngine();
  const { layersRevision, rendered, failure: layerFailure } = useMapboxSync(engine, { sites, surface });
  useMapboxSelection(engine.map, layersRevision, { sites, selectedSiteId, onSelect, onUnmappedClick });

  const extent = siteExtent(sites, { inScopeOnly: true });
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
      data-rendered-waste={rendered.waste}
    >
      <div ref={engine.containerRef} className="absolute inset-0" aria-label="Satellite map with demonstration site markers" />
      {!engine.ready && (
        <MapFallbackPlot sites={sites} selectedSiteId={selectedSiteId} onSelect={onSelect} failure={engine.failure} />
      )}
      {engine.ready && (engine.failure || layerFailure) && (
        <div role="status" className="absolute left-4 right-16 top-16 rounded bg-[var(--canvas-ink)] px-3 py-2 text-xs text-foreground">
          {layerFailure ?? engine.failure}
        </div>
      )}
      {!MAPBOX_PUBLIC_TOKEN && (
        <div className="map-token-notice">
          <Satellite size={13} />
          <span>
            <strong>Map token required</strong> for satellite imagery · synthetic geometry on a plain basemap
          </span>
        </div>
      )}
      <MapFitControl disabled={!engine.ready || extent === null} onFit={refit} />
      <MapLegend />
    </div>
  );
}
