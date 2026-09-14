import type { Metadata } from "next";
import { EquipmentFleetStatus } from "@/components/assets/EquipmentFleetStatus";
import { GhostReserveInventory } from "@/components/assets/GhostReserveInventory";
import { MineOverviewGrid } from "@/components/assets/MineOverviewGrid";

export const metadata: Metadata = { title: "Asset & Inventory Management | Mineral Intelligence" };

export default function Page() {
  return <div className="mx-auto max-w-[1800px] px-4 py-6 sm:px-7 sm:py-8">
    <header className="mb-7 flex flex-wrap items-start justify-between gap-4 border-b pb-6"><div><p className="app-kicker">05 / ASSETS</p><h1 className="app-title">Asset &amp; Inventory Management</h1><p className="app-description">A single operational view of active mines, equipment readiness and screened Ghost Reserve material.</p></div><span className="rounded-sm border border-warning bg-warning-soft px-2 py-1 text-xs font-medium text-warning">Demonstration snapshot · synthetic inventory</span></header>
    <section aria-labelledby="mine-heading"><div className="mb-3 flex items-baseline justify-between gap-3"><h2 id="mine-heading" className="text-base font-semibold">Active mine operations</h2><span className="font-mono text-xs text-muted-foreground">6 tracked sites · September 2026 scenario</span></div><MineOverviewGrid /></section>
    <section aria-labelledby="ghost-heading" className="mt-8"><div className="mb-3 flex flex-wrap items-end justify-between gap-3"><div><h2 id="ghost-heading" className="text-base font-semibold text-primary-ink">Ghost Reserve inventory</h2><p className="mt-1 text-xs text-muted-foreground">Historical waste and slag screened inside the validated occurrence context.</p></div><span className="rounded-sm border border-primary bg-primary-soft px-2 py-1 text-xs font-medium text-primary-ink">Priority material register</span></div><GhostReserveInventory /></section>
    <section aria-labelledby="fleet-heading" className="mt-8"><div className="mb-3"><h2 id="fleet-heading" className="text-base font-semibold">Equipment fleet status</h2><p className="mt-1 text-xs text-muted-foreground">Planning view of heavy machinery assigned to the operating sites.</p></div><EquipmentFleetStatus /></section>
    <p className="mt-6 border-t pt-4 text-xs leading-5 text-muted-foreground">All values are illustrative. Ghost Reserve scores are screening indices, not claims of measured ore, recoverable volume, reserve certification or environmental clearance.</p>
  </div>;
}
