import { Suspense } from "react";
import { ExplorerWorkspace } from "@/components/explorer/explorer-workspace";
import { TargetPanel, TargetPanelFallback } from "@/components/explorer/target-panel";
import { InsetBoundary } from "@/components/shell/inset-boundary";

// Sidebar/topbar and the per-request Zustand provider live in ../layout.tsx.
// Keep this route a Server Component. Mapbox is isolated behind a client boundary.
// The target ranking is computed on the server and streamed in under Suspense,
// so the map never waits for it and the browser never calls /mines.
export default function ExplorerPage() {
  return (
    <>
      <ExplorerWorkspace />
      <div className="survey-page" style={{ paddingTop: 0 }}>
        <InsetBoundary label="Greenfield targets">
          <Suspense fallback={<TargetPanelFallback />}>
            <TargetPanel />
          </Suspense>
        </InsetBoundary>
      </div>
    </>
  );
}
