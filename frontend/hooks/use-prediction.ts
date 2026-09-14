"use client";
import { useEffect, useState } from "react";
import { useExplorerStore } from "@/components/explorer/explorer-provider";
import { predictionClient } from "@/lib/api/predictions";
import type { PredictionResponse } from "@/lib/contracts";

type Result = { key: string; data: PredictionResponse | null; error: string | null };
export function usePrediction() {
  const id = useExplorerStore((s) => s.selectedSiteId);
  const mask = useExplorerStore((s) => s.activeMask);
  const key = `${id ?? "none"}:${mask}`;
  const [result, setResult] = useState<Result | null>(null);
  useEffect(() => {
    if (!id) return;
    const controller = new AbortController();
    let current = true;
    void predictionClient.predict(id, mask, controller.signal).then(
      (data) => { if (current) setResult({ key, data, error: null }); },
      (error: unknown) => {
        if (current && !controller.signal.aborted) setResult({ key, data: null, error: error instanceof Error ? error.message : "Prediction unavailable." });
      },
    );
    return () => { current = false; controller.abort(); };
  }, [id, mask, key]);
  // Hide mismatched results immediately, even before the next effect runs.
  const matched = result?.key === key;
  return { data: id && matched ? result.data : null, error: id && matched ? result.error : null, loading: Boolean(id && !matched), selected: Boolean(id) };
}
