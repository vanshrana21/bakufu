"use client";
import { useEffect, useRef, useState } from "react";
import { LocateFixed, Satellite } from "lucide-react";
import * as maplibregl from "maplibre-gl";
import type { FillLayerSpecification, GeoJSONSource } from "maplibre-gl";
import type { FeatureCollection, Point } from "geojson";
import { registerMaskPattern } from "@/lib/map/register-mask-pattern";
import { prospectivityLayers } from "@/lib/map/prospectivity-layers";
import type { MapCanvasProps } from "./map-canvas";
import { MapLegend } from "./map-legend";

const SITES = "fixture-sites";
const WASTE = "fixture-waste-sites";
const DIAGNOSTIC = "fixture-site-points";
const SURFACE = "prediction-cells";
function points(props: MapCanvasProps): FeatureCollection<Point> {
  return {
    type: "FeatureCollection",
    features: props.sites.flatMap((site) =>
      site.location && site.scope_status === "in_scope"
        ? [
            {
              type: "Feature" as const,
              id: site.id,
              properties: {
                id: site.id,
                waste: site.asset_type !== "diagnostic_point",
              },
              geometry: {
                type: "Point" as const,
                coordinates: [site.location.longitude, site.location.latitude],
              },
            },
          ]
        : [],
    ),
  };
}

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
  useEffect(() => {
    if (!container.current) return;
    let map: maplibregl.Map;
    try {
      map = new maplibregl.Map({
        container: container.current,
        center: [79.65, 21.7],
        zoom: 9.4,
        canvasContextAttributes: { preserveDrawingBuffer: true },
        style: {
          version: 8,
          sources: {},
          layers: [
            {
              id: "plain-basemap",
              type: "background",
              paint: { "background-color": "#150C0C" },
            },
          ],
        },
        attributionControl: false,
      });
    } catch {
      setFailure(
        "WebGL is unavailable. Use the screening locations below; scores remain accessible.",
      );
      return;
    }
    mapRef.current = map;
    map.addControl(
      new maplibregl.NavigationControl({ showCompass: true }),
      "top-right",
    );
    map.addControl(
      new maplibregl.ScaleControl({ unit: "metric" }),
      "bottom-left",
    );
    map.addControl(
      new maplibregl.AttributionControl({ compact: true }),
      "bottom-right",
    );
    const observer = new ResizeObserver(() => map.resize());
    observer.observe(container.current);
    const install = () => {
      // Fit display fixtures for this viewport, never treat camera bounds as scope.
      const bounds = new maplibregl.LngLatBounds();
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
      registerMaskPattern(map);
      map.addSource(SURFACE, { type: "geojson", data: latest.current.surface });
      // Both engines implement these standard v8 fill expressions. Narrow cast
      // stays at the adapter boundary; no Mapbox-only paint properties are used.
      for (const layer of prospectivityLayers("geojson"))
        map.addLayer(layer as FillLayerSpecification);
      map.addLayer({
        id: "prediction-outlines",
        type: "line",
        source: SURFACE,
        paint: {
          "line-color": "#EACEAA",
          "line-width": 1,
          "line-opacity": 0.8,
        },
      });
      map.addSource(SITES, {
        type: "geojson",
        data: points(latest.current),
        promoteId: "id",
      });
      // Sprite is local: marker rendering never depends on a remote glyph service.
      const width = 32,
        pixels = new Uint8Array(width * width * 4);
      for (let y = 0; y < width; y++)
        for (let x = 0; x < width; x++) {
          const distance = Math.abs(x - 15.5) + Math.abs(y - 15.5),
            offset = (y * width + x) * 4;
          if (distance > 14) continue;
          const border = distance > 10;
          pixels.set(
            border ? [234, 206, 170, 255] : [52, 21, 15, 255],
            offset,
          );
        }
      map.addImage(
        "waste-diamond",
        { width, height: width, data: pixels },
        { pixelRatio: 2 },
      );
      map.addLayer({
        id: "site-selection",
        type: "circle",
        source: SITES,
        paint: {
          "circle-radius": 15,
          "circle-color": "#85431E",
          "circle-stroke-color": "#D39858",
          "circle-stroke-width": 2,
          "circle-opacity": [
            "case",
            ["boolean", ["feature-state", "selected"], false],
            0.8,
            0,
          ],
          "circle-stroke-opacity": [
            "case",
            ["boolean", ["feature-state", "selected"], false],
            1,
            0,
          ],
        },
      });
      map.addLayer({
        id: DIAGNOSTIC,
        type: "circle",
        source: SITES,
        filter: ["==", ["get", "waste"], false],
        paint: {
          "circle-radius": 6,
          "circle-color": "#EACEAA",
          "circle-stroke-width": 2,
          "circle-stroke-color": "#85431E",
        },
      });
      map.addLayer({
        id: WASTE,
        type: "symbol",
        source: SITES,
        filter: ["==", ["get", "waste"], true],
        layout: {
          "icon-image": "waste-diamond",
          "icon-size": 1.3,
          "icon-allow-overlap": true,
        },
      });
      setReady(true); // Local data is ready independently of the basemap network.
      map.addSource("nasa-context", {
        type: "raster",
        tileSize: 256,
        maxzoom: 8,
        tiles: [
          "https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/BlueMarble_ShadedRelief_Bathymetry/default/GoogleMapsCompatible_Level8/{z}/{y}/{x}.jpeg",
        ],
        attribution:
          '<a href="https://earthdata.nasa.gov/centers/gibs">NASA GIBS · Blue Marble / MODIS</a>',
      });
      map.addLayer(
        {
          id: "nasa-imagery",
          type: "raster",
          source: "nasa-context",
          paint: { "raster-saturation": -0.3, "raster-brightness-max": 0.8 },
        },
        "prospectivity-screened",
      );
    };
    const counts = () => {
      if (!map.getLayer(WASTE)) return;
      const count = (layers: string[]) =>
        new Set(
          map.queryRenderedFeatures({ layers }).map((f) => f.properties.id),
        ).size;
      const next = {
        cells: count(["prospectivity-screened", "prospectivity-excluded"]),
        excluded: count(["prospectivity-excluded"]),
        waste: count([WASTE]),
      };
      setRendered((old) =>
        old.cells === next.cells &&
        old.excluded === next.excluded &&
        old.waste === next.waste
          ? old
          : next,
      );
    };
    const dataLoaded = (event: maplibregl.MapSourceDataEvent) => {
      if (event.sourceId === "nasa-context" && event.tile?.state === "loaded") {
        setImagery(true);
        setFailure(null);
      }
    };
    const onError = (event: maplibregl.ErrorEvent) => {
      if ("sourceId" in event && event.sourceId === "nasa-context")
        setFailure(
          "Satellite context unavailable. Synthetic screening layers remain usable.",
        );
      else
        setFailure(
          "A map resource could not load. Use the location list to inspect the same evidence.",
        );
    };
    const click = (event: maplibregl.MapMouseEvent) => {
      if (!map.getLayer(WASTE)) return;
      const features = map.queryRenderedFeatures(event.point, {
        layers: [WASTE, DIAGNOSTIC],
      });
      const id: unknown = features[0]?.properties.id;
      if (typeof id === "string") latest.current.onSelect(id);
      else latest.current.onUnmappedClick();
    };
    const enter = () => {
      map.getCanvas().style.cursor = "pointer";
    };
    const leave = () => {
      map.getCanvas().style.cursor = "";
    };
    map.on("load", install);
    map.on("render", counts);
    map.on("sourcedata", dataLoaded);
    map.on("error", onError);
    map.on("click", click);
    map.on("mouseenter", WASTE, enter);
    map.on("mouseleave", WASTE, leave);
    map.on("mouseenter", DIAGNOSTIC, enter);
    map.on("mouseleave", DIAGNOSTIC, leave);
    return () => {
      observer.disconnect();
      markerRef.current?.remove();
      markerRef.current = null;
      map.off("load", install);
      map.off("render", counts);
      map.off("sourcedata", dataLoaded);
      map.off("error", onError);
      map.off("click", click);
      map.off("mouseenter", WASTE, enter);
      map.off("mouseleave", WASTE, leave);
      map.off("mouseenter", DIAGNOSTIC, enter);
      map.off("mouseleave", DIAGNOSTIC, leave);
      map.remove();
      mapRef.current = null;
    };
  }, []);
  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map) return;
    (map.getSource(SITES) as GeoJSONSource).setData(points(props));
    (map.getSource(SURFACE) as GeoJSONSource).setData(props.surface);
    map.removeFeatureState({ source: SITES });
    markerRef.current?.remove();
    markerRef.current = null;
    const site = props.sites.find((s) => s.id === props.selectedSiteId);
    if (site?.location) {
      map.setFeatureState({ source: SITES, id: site.id }, { selected: true });
      const label = document.createElement("span");
      label.className = "map-site-label";
      label.textContent = site.name;
      markerRef.current = new maplibregl.Marker({
        element: label,
        anchor: "bottom",
        offset: [0, -22],
      })
        .setLngLat([site.location.longitude, site.location.latitude])
        .addTo(map);
    }
  }, [
    props.sites,
    props.activeMask,
    props.surface,
    props.selectedSiteId,
    ready,
  ]);
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
        <p
          role="status"
          className="absolute inset-x-5 top-28 text-sm text-[var(--canvas-ink)]"
        >
          {failure ?? "Loading local screening layers…"}
        </p>
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
          const bounds = new maplibregl.LngLatBounds();
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
