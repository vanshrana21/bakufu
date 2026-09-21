"use client";

import { useEffect } from "react";
import type { TargetsState } from "@/stores/explorer-store";
import { useExplorerStore } from "./explorer-provider";

/** Hands the server-ranked targets to the Explorer store. Renders nothing: the
 * map and the target list are already on screen and read the store. */
export function TargetsHydrator({ state }: { state: TargetsState }) {
  const setTargets = useExplorerStore((s) => s.setTargets);
  useEffect(() => {
    setTargets(state);
  }, [state, setTargets]);
  return null;
}
