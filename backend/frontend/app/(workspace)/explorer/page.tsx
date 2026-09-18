import { ExplorerWorkspace } from "@/components/explorer/explorer-workspace";

// Sidebar/topbar and the per-request Zustand provider live in ../layout.tsx.
// Keep this route a Server Component. Mapbox is isolated behind a client boundary.
export default function ExplorerPage() {
  return <ExplorerWorkspace />;
}
