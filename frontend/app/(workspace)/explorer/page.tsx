import { Suspense } from "react";
import { ExplorerWorkspace } from "@/components/explorer/explorer-workspace";
import { TargetsFeed } from "@/components/explorer/targets-feed";
import { loadMineLocations } from "@/lib/api/load";

// Live data on every request: mine positions from GET /mines, targets ranked
// from the served heatmap. Nothing here can be prerendered at build time.
export const dynamic = "force-dynamic";

// Sidebar/topbar and the per-request Zustand provider live in ../layout.tsx.
// Keep this route a Server Component. Mapbox is isolated behind a client boundary.
// Mines load here (one fast call) and go down as props, so the browser never
// calls /mines. The target ranking is streamed in under Suspense, so the map
// never waits for it.
export default async function ExplorerPage() {
  const mines = await loadMineLocations();
  return (
    <>
      <ExplorerWorkspace
        mines={mines.data ?? []}
        minesError={mines.error}
        minesOrigin={mines.origin}
      />
      <Suspense fallback={null}>
        <TargetsFeed />
      </Suspense>
    </>
  );
}
