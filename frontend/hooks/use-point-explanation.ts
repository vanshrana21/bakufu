"use client";

/** Score and SHAP for one coordinate, under the mask the Explorer has active.
 *
 * Both selections - an operating mine and a model target - are coordinates, so
 * one call explains either. A result is keyed by coordinate and mask, and a
 * result for anything else is hidden at once, so a slow answer can never
 * appear under a newer selection.
 */

import { useEffect, useState } from "react";
import type { MaskMode, PredictionResponse } from "@/lib/contracts";
import { LIVE_MODE } from "@/lib/api/client";
import { explainFailure, explainPoint, type Coordinate } from "@/lib/api/predictions";

export interface PointExplanation {
  data: PredictionResponse | null;
  loading: boolean;
  error: string | null;
  /** Set in a build with no backend: nothing can be scored, and nothing is invented. */
  unavailable: string | null;
}

type Settled = { key: string; data: PredictionResponse | null; error: string | null };

const NO_API = "Scoring a coordinate needs the live model; this build has no backend configured.";

export function usePointExplanation(point: Coordinate | null, mask: MaskMode): PointExplanation {
  const key = point ? `${point.latitude},${point.longitude}:${mask}` : null;
  const [settled, setSettled] = useState<Settled | null>(null);

  useEffect(() => {
    if (!point || !LIVE_MODE || key === null) return;
    const controller = new AbortController();
    let current = true;
    explainPoint(point, mask, controller.signal).then(
      (data) => { if (current) setSettled({ key, data, error: null }); },
      (error: unknown) => {
        if (current && !controller.signal.aborted) setSettled({ key, data: null, error: explainFailure(error) });
      },
    );
    return () => { current = false; controller.abort(); };
    // `key` carries both the coordinate and the mask; `point` is a new object
    // on every render and would restart the request forever.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  if (!point) return { data: null, loading: false, error: null, unavailable: null };
  if (!LIVE_MODE) return { data: null, loading: false, error: null, unavailable: NO_API };
  const matched = settled?.key === key;
  return {
    data: matched ? settled.data : null,
    error: matched ? settled.error : null,
    loading: !matched,
    unavailable: null,
  };
}
