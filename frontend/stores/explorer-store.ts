import { createStore } from "zustand/vanilla";
import type { MaskMode, TargetList } from "@/lib/contracts";

/** What the Explorer can have selected. Mines and targets use stable ids;
 * empty-ground clicks carry their exact map coordinate. */
export type SelectionKind = "mine" | "target";
export type Selection =
  | {
      kind: SelectionKind;
      /** Mine name, or target id ("T1"). Unique within its kind. */
      id: string;
    }
  | {
      kind: "point";
      id: string;
      location: { latitude: number; longitude: number };
    };

/** The ranked targets arrive after the page: the server computes them (twenty-two
 * backend calls) and streams the result in, so the map never waits for them. */
export type TargetsState =
  | { status: "loading" }
  | { status: "ready"; list: TargetList }
  | { status: "unavailable"; reason: string };

export interface ExplorerStore {
  activeMask: MaskMode;
  selected: Selection | null;
  targets: TargetsState;
  setMask: (mask: MaskMode) => void;
  select: (selection: Selection | null) => void;
  setTargets: (targets: TargetsState) => void;
}

export const createExplorerStore = () =>
  createStore<ExplorerStore>()((set) => ({
    // Geological is the mask the target ranking runs under, so the surface a
    // viewer sees matches the ground those targets were drawn from. "both"
    // additionally removes everything outside the 5 km occurrence buffer,
    // which hides precisely the greenfield ground the targets sit on.
    activeMask: "geological",
    selected: null,
    targets: { status: "loading" },
    setMask: (activeMask) => set({ activeMask }),
    select: (selected) => set({ selected }),
    // A selected target that the new ranking no longer contains is dropped,
    // so the inspector never explains a coordinate the list has stopped showing.
    setTargets: (targets) => set((state) => ({
      targets,
      selected: state.selected?.kind === "target" &&
        (targets.status !== "ready" || !targets.list.targets.some((target) => target.id === state.selected!.id))
        ? null
        : state.selected,
    })),
  }));
