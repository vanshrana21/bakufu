import { createStore } from "zustand/vanilla";
import type { MaskMode } from "@/lib/contracts";

/** What the Explorer can have selected. The two kinds are kept apart rather
 * than flattened into one id space: a mine is a place that exists, a target is
 * the model's proposal, and the inspector says which it is looking at. */
export type SelectionKind = "mine" | "target";
export interface Selection {
  kind: SelectionKind;
  /** Mine name, or target id ("T1"). Unique within its kind. */
  id: string;
}

export interface ExplorerStore {
  activeMask: MaskMode;
  selected: Selection | null;
  setMask: (mask: MaskMode) => void;
  select: (selection: Selection | null) => void;
}

export const createExplorerStore = () =>
  createStore<ExplorerStore>()((set) => ({
    // Geological is the mask the target ranking runs under, so the surface a
    // viewer sees matches the ground those targets were drawn from. "both"
    // additionally removes everything outside the 5 km occurrence buffer,
    // which hides precisely the greenfield ground the targets sit on.
    activeMask: "geological",
    selected: null,
    setMask: (activeMask) => set({ activeMask }),
    select: (selected) => set({ selected }),
  }));
