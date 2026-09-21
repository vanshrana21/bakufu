"use client";

/** Pattern matched from hooks/use-prospectivity-surface.ts: fetch on mount in
 * live mode, abort on unmount, and never fall back to a fixture — a synthetic
 * target list presented as model output is exactly the failure this app is
 * built to avoid. */

import { useEffect, useState } from "react";
import type { TargetList } from "@/lib/contracts";
import { LIVE_MODE } from "@/lib/api/client";
import { fetchTopTargets } from "@/lib/api/targets";

export interface TargetsState {
  targets: TargetList | null;
  loading: boolean;
  error: string | null;
}

export function useTopTargets(): TargetsState {
  const [state, setState] = useState<TargetsState>({
    targets: null,
    loading: LIVE_MODE,
    error: LIVE_MODE ? null : "Targets are model output, so they need the API. Set NEXT_PUBLIC_API_BASE_URL.",
  });

  useEffect(() => {
    if (!LIVE_MODE) return;
    const controller = new AbortController();
    let current = true;
    setState({ targets: null, loading: true, error: null });
    fetchTopTargets(controller.signal).then(
      (targets) => { if (current) setState({ targets, loading: false, error: null }); },
      (error: unknown) => {
        if (!current || controller.signal.aborted) return;
        setState({
          targets: null,
          loading: false,
          error: error instanceof Error ? error.message : "Target ranking failed",
        });
      },
    );
    return () => { current = false; controller.abort(); };
  }, []);

  return state;
}
