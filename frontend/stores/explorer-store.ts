import { createStore } from "zustand/vanilla";
import type { MaskMode } from "@/lib/contracts";
import { DEMO_SITES, isGhostReserveCandidate } from "@/fixtures/predictions";

export interface ExplorerStore {
  activeMask: MaskMode;
  ghostOnly: boolean;
  selectedSiteId: string | null;
  setMask: (mask: MaskMode) => void;
  setGhostOnly: (enabled: boolean) => void;
  selectSite: (id: string | null) => void;
}
export const createExplorerStore = () => createStore<ExplorerStore>()((set) => ({
  activeMask: "both", ghostOnly: false, selectedSiteId: "demo-dump-a",
  setMask: (activeMask) => set({ activeMask }),
  selectSite: (selectedSiteId) => set({ selectedSiteId }),
  setGhostOnly: (ghostOnly) => set((state) => {
    const selected = DEMO_SITES.find((s) => s.id === state.selectedSiteId);
    return { ghostOnly, selectedSiteId: ghostOnly && selected && !isGhostReserveCandidate(selected) ? null : state.selectedSiteId };
  }),
}));
