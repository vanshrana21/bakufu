"use client";

import { useEffect, useRef, useState } from "react";
import type mapboxgl from "mapbox-gl";
import type { GeoJSONSource } from "mapbox-gl";
import type { FeatureCollection, Polygon } from "geojson";
import type { SiteFixture } from "@/fixtures/predictions";
import type { CellProperties } from "@/fixtures/prospectivity-surface";
import { installMapboxLayers } from "@/lib/map/mapbox-layers";
import { MAP_IDS, renderedCounts, sameCounts, siteFeatures } from "@/lib/map/sites";
import type { MapboxEngine } from "./use-mapbox-engine";

/** How long after a source settles the counts are re-read. Long enough that a
 * burst of source events costs one read, short enough to feel immediate. */
const COUNT_SETTLE_MS = 250;

export interface MapboxSurfaces {
  sites: readonly SiteFixture[];
  /** Prospectivity cells: fixture blobs or the live heatmap, same layer spec. */
  surface: FeatureCollection<Polygon, CellProperties>;
}

export interface MapboxSync {
  /** Incremented once the sources and layers exist on the current style.
   * 0 means nothing is drawn yet. */
  layersRevision: number;
  /** What the engine actually drew, counted by unique id once the map is idle. */
  rendered: { cells: number; excluded: number; waste: number };
  /** A style/source installation failure, kept separate from tile failures. */
  failure: string | null;
}

/** Keeps the map's sources and layers in step with the data.
 *
 * Layers are installed when a style loads and reinstalled if one ever replaces
 * it; data changes only replace source contents, so the camera stays where the
 * user put it. The Ghost Reserve filter is computed once in ExplorerWorkspace
 * and passed to map and list alike.
 */
export function useMapboxSync(
  { map, styleRevision }: Pick<MapboxEngine, "map" | "styleRevision">,
  { sites, surface }: MapboxSurfaces,
): MapboxSync {
  const [layersRevision, setLayersRevision] = useState(0);
  const [rendered, setRendered] = useState({ cells: 0, excluded: 0, waste: 0 });
  const [failure, setFailure] = useState<string | null>(null);
  const latest = useRef({ sites, surface });
  const pending = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    latest.current = { sites, surface };
  }, [sites, surface]);

  // Counts settle asynchronously, so they are read once the map goes idle.
  // Subscribed before any layer exists, so no idle pass is missed.
  useEffect(() => {
    if (!map) return;
    const onSourceSettled = (event: mapboxgl.MapSourceDataEvent) => {
      if (!event.isSourceLoaded) return;
      if (pending.current !== null) clearTimeout(pending.current);
      pending.current = setTimeout(() => {
        pending.current = null;
        onIdle();
      }, COUNT_SETTLE_MS);
    };
    const onIdle = () => {
      const next = renderedCounts(
        (layers) => map.queryRenderedFeatures({ layers }),
        (id) => Boolean(map.getLayer(id)),
      );
      setRendered((previous) => (sameCounts(previous, next) ? previous : next));
    };
    map.on("idle", onIdle);
    // `idle` is the cheap path, but a map that never settles - a style swap
    // interrupted by a pan - would leave the counts stale, so a data push also
    // schedules one read.
    map.on("sourcedata", onSourceSettled);
    return () => {
      map.off("idle", onIdle);
      map.off("sourcedata", onSourceSettled);
      if (pending.current !== null) clearTimeout(pending.current);
    };
  }, [map]);

  // Sources and layers belong to a style: a new style means installing them
  // again. installMapboxLayers is idempotent, so this can only ever add.
  useEffect(() => {
    if (!map || styleRevision === 0) return;
    let active = true;
    try {
      installMapboxLayers(map, latest.current);
      if (active) {
        setFailure(null);
        setLayersRevision(styleRevision);
      }
    } catch {
      if (active) setFailure("Map layers could not be installed after the map style changed. The site list remains available.");
    }
    return () => { active = false; };
  }, [map, styleRevision]);

  // Data: replace source contents without recreating the map.
  useEffect(() => {
    if (!map || layersRevision === 0) return;
    // Guarded like the engine's callbacks: setData can race a teardown, and a
    // failure reported after unmount is a stale update, not information.
    let active = true;
    try {
      (map.getSource(MAP_IDS.sites) as GeoJSONSource | undefined)?.setData(siteFeatures(sites));
      (map.getSource(MAP_IDS.surface) as GeoJSONSource | undefined)?.setData(surface);
    } catch {
      if (active) setFailure("Map data could not be updated. The site list remains available.");
    }
    return () => {
      active = false;
    };
  }, [map, layersRevision, sites, surface]);

  return { layersRevision, rendered, failure };
}
