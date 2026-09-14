"use client";

import { useEffect, useRef, useState } from "react";
import dynamic from "next/dynamic";
import { MapLegend } from "./map-legend";
import "./map-presentation.css";
import mapboxgl, { type GeoJSONSource, type MapMouseEvent } from "mapbox-gl";
import type { FeatureCollection, Point, Polygon } from "geojson";
import { Diamond, LocateFixed, Satellite } from "lucide-react";
import type { SiteFixture } from "@/fixtures/predictions";
import type { MaskMode } from "@/lib/contracts";
import type { CellProperties } from "@/fixtures/prospectivity-surface";
import { registerMaskPattern } from "@/lib/map/register-mask-pattern";
import { prospectivityLayers } from "@/lib/map/prospectivity-layers";

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
interface SiteProperties {
  id: string;
  name: string;
  waste: boolean;
}
const SOURCE_ID = "fixture-sites";
const LAYER_ID = "fixture-site-points";
const WASTE_LAYER_ID = "fixture-waste-sites";
const publicToken = (
  process.env.NEXT_PUBLIC_MAPBOX_TOKEN ??
  process.env.NEXT_PUBLIC_MAPBOX_ACCESS_TOKEN ??
  ""
).trim();

function featureCollection(
  sites: readonly SiteFixture[],
): FeatureCollection<Point, SiteProperties> {
  return {
    type: "FeatureCollection",
    features: sites.flatMap((site) =>
      site.location && site.scope_status === "in_scope"
        ? [
            {
              type: "Feature" as const,
              id: site.id,
              geometry: {
                type: "Point" as const,
                coordinates: [site.location.longitude, site.location.latitude],
              },
              properties: {
                id: site.id,
                name: site.name,
                waste:
                  site.asset_type === "historical_waste_dump" ||
                  site.asset_type === "slag_heap",
              },
            },
          ]
        : [],
    ),
  };
}

function projectedPosition(site: SiteFixture) {
  if (!site.location) return null;
  const longitude = site.location.longitude;
  const latitude = site.location.latitude;
  const left = 18 + ((longitude - 79.15) / (80.15 - 79.15)) * 64;
  const top = 76 - ((latitude - 21.45) / (21.95 - 21.45)) * 52;
  return {
    left: `${Math.max(10, Math.min(86, left))}%`,
    top: `${Math.max(16, Math.min(82, top))}%`,
  };
}

const TokenlessMap = dynamic(() => import("./tokenless-map-canvas"), {
  ssr: false,
});
export default function MapCanvas(props: MapCanvasProps) {
  return publicToken ? (
    <MapboxCanvas {...props} />
  ) : (
    <TokenlessMap {...props} />
  );
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
  useEffect(() => {
    if (!containerRef.current) return;
    if (!mapboxgl.supported()) {
      setFailure(
        "WebGL is unavailable in this browser. Use the site list below.",
      );
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
          : {
              version: 8,
              sources: {},
              layers: [
                {
                  id: "paper-terrain",
                  type: "background",
                  paint: { "background-color": "#150C0C" },
                },
              ],
            },
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
    map.addControl(
      new mapboxgl.NavigationControl({ showCompass: false }),
      "top-right",
    );
    map.addControl(
      new mapboxgl.ScaleControl({ unit: "metric" }),
      "bottom-left",
    );
    const observer = new ResizeObserver(() => map.resize());
    observer.observe(containerRef.current);
    const timeout = setTimeout(
      () =>
        setFailure(
          "Satellite tiles are taking too long to load. The site list remains available.",
        ),
      15000,
    );

    const installLayers = () => {
      // Navigation extent only; all scope membership still comes from responses.
      if (!map.getSource(SOURCE_ID)) {
        const bounds = new mapboxgl.LngLatBounds();
        for (const site of latest.current.sites)
          if (site.location) {
            bounds.extend([
              site.location.longitude - 0.08,
              site.location.latitude - 0.07,
            ]);
            bounds.extend([
              site.location.longitude + 0.08,
              site.location.latitude + 0.07,
            ]);
          }
        if (!bounds.isEmpty())
          map.fitBounds(bounds, {
            duration: 0,
            padding: {
              top: 80,
              bottom: map.getContainer().clientWidth < 600 ? 150 : 42,
              left: 35,
              right: 45,
            },
          });
      }
      registerMaskPattern(map);
      if (!map.getSource("prediction-cells"))
        map.addSource("prediction-cells", {
          type: "geojson",
          data: latest.current.surface,
        });
      for (const layer of prospectivityLayers("geojson"))
        if (!map.getLayer(layer.id)) map.addLayer(layer);
      if (!map.getLayer("prediction-outlines"))
        map.addLayer({
          id: "prediction-outlines",
          type: "line",
          source: "prediction-cells",
          paint: {
            "line-color": "#EACEAA",
            "line-width": 1,
            "line-opacity": 0.65,
          },
        });
      if (!map.getSource(SOURCE_ID))
        map.addSource(SOURCE_ID, {
          type: "geojson",
          data: featureCollection(latest.current.sites),
          promoteId: "id",
        });
      if (!map.hasImage("waste-diamond")) {
        const icon = document.createElement("canvas");
        icon.width = 28;
        icon.height = 28;
        const context = icon.getContext("2d");
        if (context) {
          context.beginPath();
          context.moveTo(14, 3);
          context.lineTo(25, 14);
          context.lineTo(14, 25);
          context.lineTo(3, 14);
          context.closePath();
          context.fillStyle = "#34150F";
          context.fill();
          context.strokeStyle = "#EACEAA";
          context.lineWidth = 2;
          context.stroke();
          map.addImage(
            "waste-diamond",
            {
              width: 28,
              height: 28,
              data: new Uint8Array(context.getImageData(0, 0, 28, 28).data),
            },
            { pixelRatio: 2 },
          );
        }
      }
      if (!map.getLayer("site-selection"))
        map.addLayer({
          id: "site-selection",
          type: "circle",
          source: SOURCE_ID,
          paint: {
            "circle-radius": 15,
            "circle-color": "#85431E",
            "circle-opacity": [
              "case",
              ["boolean", ["feature-state", "selected"], false],
              0.85,
              0,
            ],
            "circle-stroke-color": "#D39858",
            "circle-stroke-width": 2,
            "circle-stroke-opacity": [
              "case",
              ["boolean", ["feature-state", "selected"], false],
              1,
              0,
            ],
          },
        });
      if (!map.getLayer(LAYER_ID))
        map.addLayer({
          id: LAYER_ID,
          type: "circle",
          source: SOURCE_ID,
          filter: ["==", ["get", "waste"], false],
          paint: {
            "circle-radius": 6,
            "circle-color": "#EACEAA",
            "circle-stroke-color": "#EACEAA",
            "circle-stroke-width": 1,
          },
        });
      if (!map.getLayer(WASTE_LAYER_ID) && map.hasImage("waste-diamond"))
        map.addLayer({
          id: WASTE_LAYER_ID,
          type: "symbol",
          source: SOURCE_ID,
          filter: ["==", ["get", "waste"], true],
          layout: {
            "icon-image": "waste-diamond",
            "icon-size": 1.2,
            "icon-allow-overlap": true,
          },
        });
      // Mock footprint geometry only. Replace this source with versioned vector
      // tiles when supplied; retain the same layer specs and null-score gates.
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
      // Expose actual rendered feature counts for accessible diagnostics and E2E,
      // not just the input counts. Source updates settle asynchronously.
      const count = (layers: string[]) =>
        new Set(
          map
            .queryRenderedFeatures({
              layers: layers.filter((id) => map.getLayer(id)),
            })
            .map((f) => f.properties?.id),
        ).size;
      const next = {
        cells: count(["prospectivity-screened", "prospectivity-excluded"]),
        excluded: count(["prospectivity-excluded"]),
        waste: count([WASTE_LAYER_ID]),
      };
      setRendered((previous) =>
        previous.cells === next.cells &&
        previous.excluded === next.excluded &&
        previous.waste === next.waste
          ? previous
          : next,
      );
    };
    const onClick = (event: MapMouseEvent) => {
      const layers = [LAYER_ID, WASTE_LAYER_ID].filter((id) =>
        map.getLayer(id),
      );
      const feature = layers.length
        ? map.queryRenderedFeatures(event.point, { layers })[0]
        : undefined;
      const id: unknown = feature?.properties?.id;
      if (typeof id === "string") latest.current.onSelect(id);
      else {
        // SAUSAR SCOPE CHECK for arbitrary coordinates belongs in the backend
        // point-query response. Never treat the camera extent as validated scope.
        latest.current.onUnmappedClick();
      }
    };
    const onEnter = () => {
      map.getCanvas().style.cursor = "pointer";
    };
    const onLeave = () => {
      map.getCanvas().style.cursor = "";
    };
    map.on("style.load", installLayers);
    map.on("load", onLoad);
    map.on("error", onError);
    map.on("idle", onIdle);
    map.on("click", onClick);
    map.on("mouseenter", LAYER_ID, onEnter);
    map.on("mouseleave", LAYER_ID, onLeave);
    map.on("mouseenter", WASTE_LAYER_ID, onEnter);
    map.on("mouseleave", WASTE_LAYER_ID, onLeave);
    return () => {
      clearTimeout(timeout);
      observer.disconnect();
      markerRef.current?.remove();
      markerRef.current = null;
      map.off("style.load", installLayers);
      map.off("load", onLoad);
      map.off("error", onError);
      map.off("idle", onIdle);
      map.off("click", onClick);
      map.off("mouseenter", LAYER_ID, onEnter);
      map.off("mouseleave", LAYER_ID, onLeave);
      map.off("mouseenter", WASTE_LAYER_ID, onEnter);
      map.off("mouseleave", WASTE_LAYER_ID, onLeave);
      map.remove();
      mapRef.current = null;
    };
  }, []);

  useEffect(() => {
    const source = mapRef.current?.getSource(SOURCE_ID) as
      GeoJSONSource | undefined;
    // GHOST RESERVE FILTER is computed once in ExplorerWorkspace and passed to
    // both map and site list. This update changes data without recreating Mapbox.
    source?.setData(featureCollection(props.sites));
    const surface = mapRef.current?.getSource("prediction-cells") as
      GeoJSONSource | undefined;
    surface?.setData(props.surface);
  }, [props.sites, props.activeMask, props.surface, styleRevision]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map?.getSource(SOURCE_ID)) return;
    if (previousSelection.current)
      map.setFeatureState(
        { source: SOURCE_ID, id: previousSelection.current },
        { selected: false },
      );
    if (props.selectedSiteId)
      map.setFeatureState(
        { source: SOURCE_ID, id: props.selectedSiteId },
        { selected: true },
      );
    previousSelection.current = props.selectedSiteId;
    markerRef.current?.remove();
    markerRef.current = null;
    const site = props.sites.find(
      (candidate) => candidate.id === props.selectedSiteId,
    );
    if (site?.location) {
      const label = document.createElement("span");
      label.className = "map-site-label";
      label.textContent = site.name;
      markerRef.current = new mapboxgl.Marker({
        element: label,
        anchor: "bottom",
        offset: [0, -22],
      })
        .setLngLat([site.location.longitude, site.location.latitude])
        .addTo(map);
    }
    // Deliberately preserve the camera when masks or inspector contents change.
  }, [props.selectedSiteId, props.sites, styleRevision]);

  return (
    <div
      className="map-presentation absolute inset-0"
      data-testid="map-render-state"
      data-ready={ready}
      data-rendered-cells={rendered.cells}
      data-rendered-excluded={rendered.excluded}
      data-rendered-waste={rendered.waste}
    >
      <div
        ref={containerRef}
        className="absolute inset-0"
        aria-label="Satellite map with demonstration site markers"
      />
      {!ready && (
        <div className="absolute inset-0 overflow-hidden bg-[var(--canvas)] text-[var(--canvas-ink)]">
          <div
            className="absolute left-[18%] right-[18%] top-[24%] bottom-[24%] border border-[var(--map-out-of-scope)]"
            aria-hidden="true"
          >
            <div className="absolute inset-x-0 top-1/2 border-t border-[var(--map-out-of-scope)]" />
            <div className="absolute inset-y-0 left-1/2 border-l border-[var(--map-out-of-scope)]" />
            <span className="absolute -left-14 -top-2 text-xs text-[var(--canvas-muted)]">
              21.95°
            </span>
            <span className="absolute -left-14 bottom-0 text-xs text-[var(--canvas-muted)]">
              21.45°
            </span>
            <span className="absolute -bottom-6 left-0 text-xs text-[var(--canvas-muted)]">
              79.15° E
            </span>
            <span className="absolute -bottom-6 right-0 text-xs text-[var(--canvas-muted)]">
              80.15° E
            </span>
          </div>
          {props.sites.map((site) => {
            const position = projectedPosition(site);
            if (!position) return null;
            const active = props.selectedSiteId === site.id;
            return (
              <button
                key={site.id}
                type="button"
                onClick={() => props.onSelect(site.id)}
                aria-label={`Inspect ${site.name}`}
                aria-pressed={active}
                className="absolute z-10 flex h-8 w-8 -translate-x-1/2 -translate-y-1/2 items-center justify-center focus-visible:outline-[var(--canvas-ink)]"
                style={position}
              >
                <span
                  className={`flex h-7 w-7 items-center justify-center rounded-full ${active ? "border-2 border-[var(--canvas-ink)] bg-[var(--canvas)]" : ""}`}
                >
                  {site.asset_type === "diagnostic_point" ? (
                    <span className="h-3 w-3 rounded-full border border-[var(--canvas-ink)] bg-[var(--canvas-muted)]" />
                  ) : (
                    <Diamond
                      size={18}
                      fill="var(--map-ghost)"
                      stroke="#EACEAA"
                      strokeWidth={1.5}
                    />
                  )}
                </span>
                {active && (
                  <span
                    className={`absolute top-8 w-max max-w-48 rounded-md border border-[var(--map-out-of-scope)] bg-[var(--canvas)] px-3 py-2 text-left text-xs text-[var(--canvas-ink)] ${Number.parseFloat(position.left) > 60 ? "right-0" : "left-0"}`}
                  >
                    {site.name}
                  </span>
                )}
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
              <span className="hidden sm:inline">
                · Coordinate plot of demonstration sites
              </span>
            </p>
            <p className="sr-only">
              {failure ?? "The site selection workflow remains available."}
            </p>
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
            <strong>Map token required</strong> for satellite imagery ·
            synthetic geometry on a plain basemap
          </span>
        </div>
      )}
      <button
        type="button"
        className="map-fit-control"
        aria-label="Fit screening locations"
        title="Fit screening locations"
        disabled={
          !ready ||
          !props.sites.some(
            (site) => site.location && site.scope_status === "in_scope",
          )
        }
        onClick={() => {
          const map = mapRef.current;
          if (!map) return;
          const bounds = new mapboxgl.LngLatBounds();
          for (const site of props.sites)
            if (site.location && site.scope_status === "in_scope") {
              bounds.extend([
                site.location.longitude - 0.08,
                site.location.latitude - 0.07,
              ]);
              bounds.extend([
                site.location.longitude + 0.08,
                site.location.latitude + 0.07,
              ]);
            }
          if (!bounds.isEmpty())
            map.fitBounds(bounds, {
              duration: window.matchMedia("(prefers-reduced-motion: reduce)")
                .matches
                ? 0
                : 500,
              padding: {
                top: 90,
                bottom: map.getContainer().clientWidth < 600 ? 170 : 75,
                left: 35,
                right: 45,
              },
            });
        }}
      >
        <LocateFixed size={17} />
      </button>
      <MapLegend />
    </div>
  );
}
