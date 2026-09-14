import type { Metadata } from "next";
import { IngestionStatusGrid } from "@/components/pipeline/IngestionStatusGrid";
import { ModelVersionRegistry } from "@/components/pipeline/ModelVersionRegistry";
import { RetrainingLog } from "@/components/pipeline/RetrainingLog";

export const metadata: Metadata = { title: "Data Pipeline & Ingestion Monitor | Mineral Intelligence" };

export default function Page() {
  return <div className="mx-auto max-w-[1800px] px-4 py-6 sm:px-7 sm:py-8">
    <header className="mb-7 flex flex-wrap items-start justify-between gap-4 border-b pb-6"><div><p className="app-kicker">07 / PIPELINE</p><h1 className="app-title">Data Pipeline &amp; Ingestion Monitor</h1><p className="app-description">A transparent view of source freshness, model versions and the evidence trail behind retraining.</p></div><span className="rounded-sm border border-warning bg-warning-soft px-2 py-1 text-xs font-medium text-warning">Demonstration snapshot · synthetic metadata</span></header>
    <section aria-labelledby="ingestion-heading"><div className="mb-3 flex items-baseline justify-between gap-3"><h2 id="ingestion-heading" className="text-base font-semibold">Data ingestion health</h2><span className="font-mono text-xs text-muted-foreground">Last checked · 12 Sep 2026 09:45 UTC</span></div><IngestionStatusGrid /></section>
    <section aria-labelledby="registry-heading" className="mt-8"><div className="mb-3"><h2 id="registry-heading" className="text-base font-semibold">Model registry</h2><p className="mt-1 text-xs text-muted-foreground">Versioned artifacts with validation evidence and deployment state.</p></div><ModelVersionRegistry /></section>
    <section aria-labelledby="retraining-heading" className="mt-8"><div className="mb-3"><h2 id="retraining-heading" className="text-base font-semibold">Active learning &amp; retraining log</h2><p className="mt-1 text-xs text-muted-foreground">Operational events that can pause, stage or initiate a model update.</p></div><RetrainingLog /></section>
    <p className="mt-6 border-t pt-4 text-xs leading-5 text-muted-foreground">These records are illustrative. A deployed status does not certify generalization beyond the validated Sausar Belt scope; triggers and actions require the corresponding backend workflow.</p>
  </div>;
}
