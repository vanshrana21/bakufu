import type { ReactNode } from "react";
import { AppShell } from "@/components/shell/app-shell";
import { ExplorerProvider } from "@/components/explorer/explorer-provider";
// ReviewRegister, ProductionChart, RiskGauge and ActionEvidence render on every
// route, so their styles load once here rather than per page. A page-level import
// would leave the same components unstyled on the routes that omit it.
import "@/components/operations/operations.css";
import "@/components/shell/workspace.css";

export default function WorkspaceLayout({ children }: { children: ReactNode }) {
  return <ExplorerProvider><AppShell>{children}</AppShell></ExplorerProvider>;
}
