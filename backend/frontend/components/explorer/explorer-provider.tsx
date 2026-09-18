"use client";

import { createContext, useContext, useState, type ReactNode } from "react";
import { useStore } from "zustand";
import { createExplorerStore, type ExplorerStore } from "@/stores/explorer-store";

type StoreApi = ReturnType<typeof createExplorerStore>;
const ExplorerContext = createContext<StoreApi | null>(null);
export function ExplorerProvider({ children }: { children: ReactNode }) {
  // One store per mounted provider / SSR request, never shared server module state.
  const [store] = useState(createExplorerStore);
  return <ExplorerContext.Provider value={store}>{children}</ExplorerContext.Provider>;
}
export function useExplorerStore<T>(selector: (state: ExplorerStore) => T): T {
  const store = useContext(ExplorerContext);
  if (!store) throw new Error("ExplorerProvider is missing.");
  return useStore(store, selector);
}
