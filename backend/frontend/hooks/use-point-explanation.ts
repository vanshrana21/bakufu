"use client";

/** Score and SHAP for one coordinate, under the mask the Explorer has active.
 *
 * Replaces hooks/use-prediction.ts, which scored hand-placed fixture sites.
 * Both selections — an operating mine and a model target — are just
 * coordinates, so one call serves both and the mask toggles apply to each.
 */

import { useEffect, useState } from "react";
import type { WirePredictPoint } from "@/lib/api/wire";
import type { MaskMode } from "@/lib/contracts";
import { ApiRequestError, LIVE_MODE, PREDICT_POINT_TIMEOUT_MS, apiPost } from "@/lib/api/client";

export interface PointExplanation {
  rawScore: number;
  finalScore: number;
  /** Uncapped classifier output. Null on a backend older than v1.10. */
  margin: number | null;
  rawProbability: number | null;
  maskApplied: string;
  maskDecision: string;
  modelVersion: string;
  drivers: Array<{ feature: string; label: string; contribution: number; observed: number }>;
}

export interface PointExplanationState {
  data: PointExplanation | null;
  loading: boolean;
  /** Set when the backend has no imagery there: a stated absence, not a zero. */
  noImagery: boolean;
  error: string | null;
}

const IDLE: PointExplanationState = { data: null, loading: false, noImagery: false, error: null };

export function usePointExplanation(
  point: { latitude: number; longitude: number } | null,
  mask: MaskMode,
): PointExplanationState {
  const [state, setState] = useState<PointExplanationState>(IDLE);
  const key = point ? `${point.latitude},${point.longitude}:${mask}` : null;

  useEffect(() => {
    if (!point || !LIVE_MODE) {
      setState(point && !LIVE_MODE
        ? { ...IDLE, error: "Scoring a coordinate needs the API." }
        : IDLE);
      return;
    }
    const controller = new AbortController();
    let current = true;
    setState({ data: null, loading: true, noImagery: false, error: null });
    apiPost<WirePredictPoint>(
      "/predict/point",
      { lat: point.latitude, lon: point.longitude },
      { query: { mask }, timeoutMs: PREDICT_POINT_TIMEOUT_MS, signal: controller.signal },
    ).then(
      (wire) => {
        if (!current) return;
        setState({
          data: {
            rawScore: wire.raw_score ?? wire.prospectivity_score,
            finalScore: wire.final_score ?? wire.prospectivity_score,
            margin: typeof wire.model_margin === "number" ? wire.model_margin : null,
            rawProbability:
              typeof wire.raw_probability === "number" ? wire.raw_probability : null,
            maskApplied: wire.mask_applied,
            maskDecision: wire.mask_decision,
            modelVersion: wire.model_version,
            drivers: wire.shap_top5.map((row) => ({
              feature: row.feature,
              label: row.feature.replaceAll("_", " "),
              contribution: row.shap_value,
              observed: row.actual_value,
            })),
          },
          loading: false, noImagery: false, error: null,
        });
      },
      (error: unknown) => {
        if (!current || controller.signal.aborted) return;
        const noImagery =
          error instanceof ApiRequestError && error.code === "no_imagery_at_location";
        setState({
          data: null,
          loading: false,
          noImagery,
          error: error instanceof Error ? error.message : "Scoring failed",
        });
      },
    );
    return () => { current = false; controller.abort(); };
    // `key` carries both the coordinate and the mask; `point` is a new object
    // on every render and would restart the request forever.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  return state;
}
