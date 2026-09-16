"use client";

import { useEffect, useRef, useState, type RefObject } from "react";
import mapboxgl from "mapbox-gl";

/** The public token, read once. Empty when none is configured, which is what
 * sends the Explorer to the open MapLibre renderer instead. */
export const MAPBOX_PUBLIC_TOKEN = (
  process.env.NEXT_PUBLIC_MAPBOX_TOKEN ??
  process.env.NEXT_PUBLIC_MAPBOX_ACCESS_TOKEN ??
  ""
).trim();

/** How long tiles may take before the fallback plot says so. */
const TILE_TIMEOUT_MS = 15_000;

export interface MapboxEngine {
  /** Attach to the element the map draws into. */
  containerRef: RefObject<HTMLDivElement>;
  /** The live map, or null before it is created and after it is torn down. */
  map: mapboxgl.Map | null;
  /** True once `load` has fired: style, first tiles and first frame are done. */
  ready: boolean;
  /** Set when WebGL, the token or a resource failed. */
  failure: string | null;
  /** Incremented on every `style.load`. 0 means no style has loaded yet.
   * Layers live on a style, so everything that draws re-applies on a change. */
  styleRevision: number;
}

/** Owns the Mapbox map itself: the container, the token, the instance and its
 * lifecycle events. It draws nothing - use-mapbox-sync adds the sources and
 * layers, use-mapbox-selection the clicks and markers - so the map survives
 * every data change, keeping its WebGL context and wherever the user put the
 * camera.
 */
export function useMapboxEngine(token: string = MAPBOX_PUBLIC_TOKEN): MapboxEngine {
  const containerRef = useRef<HTMLDivElement>(null);
  const [map, setMap] = useState<mapboxgl.Map | null>(null);
  const [ready, setReady] = useState(false);
  const [failure, setFailure] = useState<string | null>(null);
  const [styleRevision, setStyleRevision] = useState(0);
  const generation = useRef(0);

  // Created once, torn down on unmount. The token cannot change at runtime:
  // it is baked in at build time.
  useEffect(() => {
    const currentGeneration = ++generation.current;
    let active = true;
    const guarded = (callback: () => void) => {
      if (active && generation.current === currentGeneration) callback();
    };
    if (!containerRef.current) return;
    if (!mapboxgl.supported()) {
      guarded(() => setFailure("WebGL is unavailable in this browser. Use the site list below."));
      return;
    }
    let instance: mapboxgl.Map;
    try {
      instance = new mapboxgl.Map({
        container: containerRef.current,
        accessToken: token || undefined,
        // Satellite imagery needs the user's public token. The local style still
        // renders and exercises all mock GeoJSON layers offline without one.
        style: token
          ? "mapbox://styles/mapbox/satellite-streets-v12"
          : { version: 8, sources: {}, layers: [{ id: "paper-terrain", type: "background", paint: { "background-color": "#150C0C" } }] },
        center: [79.65, 21.7],
        zoom: 9.4,
        // This camera is navigation only—not a Sausar validation boundary.
        attributionControl: true,
        preserveDrawingBuffer: true,
      });
    } catch {
      guarded(() => setFailure("The map could not initialize. Use the site list below."));
      return;
    }
    instance.addControl(new mapboxgl.NavigationControl({ showCompass: false }), "top-right");
    instance.addControl(new mapboxgl.ScaleControl({ unit: "metric" }), "bottom-left");
    const observer = new ResizeObserver(() => instance.resize());
    observer.observe(containerRef.current);
    const timeout = setTimeout(
      () => guarded(() => setFailure("Satellite tiles are taking too long to load. The site list remains available.")),
      TILE_TIMEOUT_MS,
    );

    const onStyleLoad = () => guarded(() => setStyleRevision((revision) => revision + 1));
    const onLoad = () => guarded(() => {
      clearTimeout(timeout);
      setReady(true);
      setFailure(null);
    });
    const onError = (event: mapboxgl.ErrorEvent) => guarded(() => {
      if (event.error.message.includes("access token")) setReady(false);
      setFailure(
        "Some map resources could not load. Check the public token, allowed URLs and network. The site list remains available.",
      );
    });

    instance.on("style.load", onStyleLoad);
    instance.on("load", onLoad);
    instance.on("error", onError);
    setMap(instance);
    return () => {
      active = false;
      generation.current++;
      clearTimeout(timeout);
      observer.disconnect();
      instance.off("style.load", onStyleLoad);
      instance.off("load", onLoad);
      instance.off("error", onError);
      instance.remove();
      setMap(null);
      setReady(false);
      setStyleRevision(0);
    };
  }, [token]);

  return { containerRef, map, ready, failure, styleRevision };
}
