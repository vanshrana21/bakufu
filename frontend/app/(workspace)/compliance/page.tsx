import type { Metadata } from "next";
import { AuditLogTimeline } from "@/components/compliance/AuditLogTimeline";
import { ComplianceOverviewGrid } from "@/components/compliance/ComplianceOverviewGrid";
import { PermitRegistryTable } from "@/components/compliance/PermitRegistryTable";

export const metadata: Metadata = { title: "Regulatory & Compliance Tracker | Mineral Intelligence" };

export default function Page() {
  return <div className="mx-auto max-w-[1800px] px-4 py-6 sm:px-7 sm:py-8">
    <header className="mb-7 flex flex-wrap items-start justify-between gap-4 border-b pb-6"><div><p className="app-kicker">08 / COMPLIANCE</p><h1 className="app-title">Regulatory &amp; Compliance Tracker</h1><p className="app-description">Keep permits, clearances and safety findings visible before they become operational blockers.</p></div><span className="rounded-sm border border-warning bg-warning-soft px-2 py-1 text-xs font-medium text-warning">Demonstration snapshot · verify before action</span></header>
    <section aria-labelledby="compliance-health-heading"><div className="mb-3 flex items-baseline justify-between gap-3"><h2 id="compliance-health-heading" className="text-base font-semibold">Compliance health overview</h2><span className="font-mono text-xs text-muted-foreground">Last reviewed · 12 Sep 2026</span></div><ComplianceOverviewGrid /></section>
    <section aria-labelledby="permit-heading" className="mt-8"><div className="mb-3"><h2 id="permit-heading" className="text-base font-semibold">Permit &amp; clearance registry</h2><p className="mt-1 text-xs text-muted-foreground">Renewal urgency is shown for review; authoritative records remain the source of legal status.</p></div><PermitRegistryTable /></section>
    <section aria-labelledby="audit-heading" className="mt-8"><div className="mb-3"><h2 id="audit-heading" className="text-base font-semibold">Recent audit &amp; inspection log</h2><p className="mt-1 text-xs text-muted-foreground">A chronological evidence trail for site checks, submissions and open findings.</p></div><AuditLogTimeline /></section>
    <p className="mt-6 border-t pt-4 text-xs leading-5 text-muted-foreground">All entries are illustrative planning metadata. This page does not grant clearance, certify compliance or replace MoEFCC, DGMS, MPCB, CGWA or IBM records.</p>
  </div>;
}
