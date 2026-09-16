"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import type { FeatureCollection, Polygon } from "geojson";
import type { MaskMode } from "@/lib/contracts";
import type { SiteFixture } from "@/fixtures/predictions";
import { buildProspectivitySurface, type CellProperties } from "@/fixtures/prospectivity-surface";
import { LIVE_MODE } from "@/lib/api/client";
import { WARM_VIEWPORTS, fetchHeatmap } from "@/lib/api/heatmap";

export interface SurfaceState {
  surface: FeatureCollection<Polygon, CellProperties>;
  loading: boolean;
  error: string | null;
  origin: "live" | "fixture";
  /** True when the backend served this from its own cache, i.e. a warm hit. */
  cached: boolean;
  /** Set when mask exclusions could not be attributed per-cell — see
   * lib/api/heatmap.ts. Surfaced so the map never silently drops the hatch. */
  note: string | null;
  cellsScored: number | null;
  cellsNoData: number | null;
}

const EMPTY: FeatureCollection<Polygon, CellProperties> = { type: "FeatureCollection", features: [] };

/** The prospectivity surface for the map.
 *
 * Fixture mode returns the synthetic blobs immediately. Live mode fetches the
 * pre-warmed `full_bbox` viewport, which the backend warms at startup — the
 * documented cold path is ~38s, and requesting a viewport it did not warm is
 * what makes the map look hung.
 */
export function useProspectivitySurface(sites: readonly SiteFixture[], mask: MaskMode): SurfaceState {
  const fixtureSurface = useMemo(() => buildProspectivitySurface(sites, mask), [sites, mask]);
  const [state, setState] = useState<Omit<SurfaceState, "surface"> & { surface: FeatureCollection<Polygon, CellProperties> | null }>({
    surface: null, loading: LIVE_MODE, error: null, origin: LIVE_MODE ? "live" : "fixture",
    cached: false, note: null, cellsScored: null, cellsNoData: null,
  });
  const requestGeneration = useRef(0);

  useEffect(() => {
    if (!LIVE_MODE) return;
    const generation = ++requestGeneration.current;
    const controller = new AbortController();
    const current = () => requestGeneration.current === generation && !controller.signal.aborted;
    setState((previous) => ({ ...previous, surface: null, loading: true, error: null }));
    fetchHeatmap({ ...WARM_VIEWPORTS.full_bbox, gridSize: 32, mask, signal: controller.signal }).then(
      (result) => {
        if (!current()) return;
        setState({
          surface: result.surface, loading: false, error: null, origin: "live",
          cached: result.cached, note: result.maskExclusionNote,
          cellsScored: result.cells.cells_scored,
          cellsNoData: result.cells.cells_outside_raster,
        });
      },
      (error: unknown) => {
        if (!current()) return;
        // No fixture fallback: a synthetic surface presented as live model
        // output is the one failure mode this map must never have.
        setState({
          surface: null, loading: false, origin: "live", cached: false, note: null,
          cellsScored: null, cellsNoData: null,
          error: error instanceof Error ? error.message : "Prospectivity surface unavailable.",
        });
      },
    );
    return () => {
      controller.abort();
      // Invalidate even fetch implementations that incorrectly resolve after abort.
      requestGeneration.current++;
    };
  }, [mask]);

  if (!LIVE_MODE) {
    return {
      surface: fixtureSurface, loading: false, error: null, origin: "fixture",
      cached: false, note: null, cellsScored: null, cellsNoData: null,
    };
  }
  return { ...state, surface: state.surface ?? EMPTY };
}
