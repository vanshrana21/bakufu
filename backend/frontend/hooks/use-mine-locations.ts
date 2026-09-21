"use client";

/** Pattern matched from hooks/use-prospectivity-surface.ts: fetch on mount in
 * live mode, abort on unmount, no fixture fallback. */

import { useEffect, useState } from "react";
import type { MineLocation } from "@/lib/contracts";
import { LIVE_MODE } from "@/lib/api/client";
import { fetchMineLocations } from "@/lib/api/mines";

export interface MineLocationsState {
  mines: readonly MineLocation[];
  loading: boolean;
  error: string | null;
}

export function useMineLocations(): MineLocationsState {
  const [state, setState] = useState<MineLocationsState>({
    mines: [],
    loading: LIVE_MODE,
    error: LIVE_MODE ? null : "Mine positions come from GET /mines, so they need the API.",
  });

  useEffect(() => {
    if (!LIVE_MODE) return;
    const controller = new AbortController();
    let current = true;
    fetchMineLocations(controller.signal).then(
      (mines) => { if (current) setState({ mines, loading: false, error: null }); },
      (error: unknown) => {
        if (!current || controller.signal.aborted) return;
        setState({
          mines: [],
          loading: false,
          error: error instanceof Error ? error.message : "Mine roster unavailable",
        });
      },
    );
    return () => { current = false; controller.abort(); };
  }, []);

  return state;
}
