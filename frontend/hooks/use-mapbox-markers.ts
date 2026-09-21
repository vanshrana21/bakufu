"use client";

import { useEffect, useRef } from "react";
import mapboxgl from "mapbox-gl";
import { renderMarkers, type MarkerConstructor, type MarkerLayerOptions } from "@/components/explorer/map-markers";

export interface MapboxMarkers extends MarkerLayerOptions {
  /** A click that hit no marker, forwarded to point scoring. */
  onUnmappedClick: (location: {
    latitude: number;
    longitude: number;
  }) => void;
}

/** Draws the mine and target markers and turns clicks into selections.
 *
 * Markers are DOM elements, so unlike layers they survive a style swap and
 * need no reinstall: they are redrawn only when the data or the selection
 * changes.
 */
export function useMapboxMarkers(
  map: mapboxgl.Map | null,
  { mines, targets, selected, onSelect, onUnmappedClick }: MapboxMarkers,
): void {
  const handlers = useRef({ onSelect, onUnmappedClick });

  useEffect(() => {
    handlers.current = { onSelect, onUnmappedClick };
  }, [onSelect, onUnmappedClick]);

  // Markers stop their own clicks, so anything reaching the map is empty ground.
  useEffect(() => {
    if (!map) return;
    const onClick = (event: mapboxgl.MapMouseEvent) =>
      handlers.current.onUnmappedClick({
        latitude: event.lngLat.lat,
        longitude: event.lngLat.lng,
      });
    map.on("click", onClick);
    return () => {
      map.off("click", onClick);
    };
  }, [map]);

  useEffect(() => {
    if (!map) return;
    return renderMarkers(map, mapboxgl.Marker as unknown as MarkerConstructor, {
      mines,
      targets,
      selected,
      onSelect: (selection) => handlers.current.onSelect(selection),
    });
  }, [map, mines, targets, selected]);
}
