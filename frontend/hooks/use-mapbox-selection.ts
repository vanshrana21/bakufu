"use client";

import { useEffect, useRef, useState } from "react";
import mapboxgl, { type MapMouseEvent } from "mapbox-gl";
import type { SiteFixture } from "@/fixtures/predictions";
import { MAP_IDS, SITE_LABEL_MARKER, siteLabelElement } from "@/lib/map/sites";

/** The only layers a click can resolve to a site. */
const CLICKABLE_LAYERS = [MAP_IDS.diagnosticLayer, MAP_IDS.wasteLayer];

/** How long to wait before reapplying a selection a style change interrupted. */
const SELECTION_RETRY_MS = 120;

export interface MapboxSelection {
  sites: readonly SiteFixture[];
  selectedSiteId: string | null;
  onSelect: (siteId: string) => void;
  /** A click that hit no site: arbitrary coordinates need the live API. */
  onUnmappedClick: () => void;
}

/** Turns clicks into selections and draws the selected site.
 *
 * `layersRevision` comes from use-mapbox-sync: feature state and the name tag
 * need the sites source to exist, and have to be reapplied whenever the layers
 * are installed again.
 */
export function useMapboxSelection(
  map: mapboxgl.Map | null,
  layersRevision: number,
  { sites, selectedSiteId, onSelect, onUnmappedClick }: MapboxSelection,
): void {
  const [attempt, setAttempt] = useState(0);
  const markerRef = useRef<mapboxgl.Marker | null>(null);
  const previousSelection = useRef<string | null>(null);
  const handlers = useRef({ onSelect, onUnmappedClick });

  useEffect(() => {
    handlers.current = { onSelect, onUnmappedClick };
  }, [onSelect, onUnmappedClick]);

  // Click and cursor handling, bound to the map rather than to a layer that
  // may not exist yet.
  useEffect(() => {
    if (!map) return;
    const onClick = (event: MapMouseEvent) => {
      const layers = CLICKABLE_LAYERS.filter((id) => map.getLayer(id));
      const feature = layers.length ? map.queryRenderedFeatures(event.point, { layers })[0] : undefined;
      const id: unknown = feature?.properties?.id;
      if (typeof id === "string") handlers.current.onSelect(id);
      // SAUSAR SCOPE CHECK for arbitrary coordinates belongs in the backend
      // point-query response. Never treat the camera extent as validated scope.
      else handlers.current.onUnmappedClick();
    };
    const onEnter = () => {
      map.getCanvas().style.cursor = "pointer";
    };
    const onLeave = () => {
      map.getCanvas().style.cursor = "";
    };

    map.on("click", onClick);
    for (const layer of CLICKABLE_LAYERS) {
      map.on("mouseenter", layer, onEnter);
      map.on("mouseleave", layer, onLeave);
    }
    return () => {
      map.off("click", onClick);
      for (const layer of CLICKABLE_LAYERS) {
        map.off("mouseenter", layer, onEnter);
        map.off("mouseleave", layer, onLeave);
      }
      markerRef.current?.remove();
      markerRef.current = null;
      previousSelection.current = null;
    };
  }, [map]);

  // Highlight the chosen site and tag it with its name. The camera is
  // deliberately left where the user put it.
  useEffect(() => {
    if (!map || layersRevision === 0 || !map.getSource(MAP_IDS.sites)) return;
    let active = true;
    // A style replacement removes feature state even though the selected id is
    // unchanged. Reapply it only while this installation is still current.
    try {
      if (previousSelection.current) {
        map.setFeatureState({ source: MAP_IDS.sites, id: previousSelection.current }, { selected: false });
      }
      if (active && selectedSiteId && map.getSource(MAP_IDS.sites)) {
        map.setFeatureState({ source: MAP_IDS.sites, id: selectedSiteId }, { selected: true });
      }
    } catch {
      // A style swap can pull the source out from under this. Retry shortly
      // rather than leaving the selection invisible until something else
      // happens to change: the user's choice is still the current one.
      const retry = setTimeout(() => setAttempt((count) => count + 1), SELECTION_RETRY_MS);
      return () => {
        active = false;
        clearTimeout(retry);
      };
    }
    previousSelection.current = selectedSiteId;
    markerRef.current?.remove();
    markerRef.current = null;
    const site = sites.find((candidate) => candidate.id === selectedSiteId);
    if (site?.location) {
      try {
        markerRef.current = new mapboxgl.Marker({ element: siteLabelElement(site.name), ...SITE_LABEL_MARKER })
          .setLngLat([site.location.longitude, site.location.latitude])
          .addTo(map);
      } catch {
        // A style or container teardown can race marker installation; the same
        // retry brings the name tag back.
        markerRef.current = null;
        const retry = setTimeout(() => setAttempt((count) => count + 1), SELECTION_RETRY_MS);
        return () => {
          active = false;
          clearTimeout(retry);
        };
      }
    }
    return () => { active = false; };
  }, [map, layersRevision, selectedSiteId, sites, attempt]);
}
