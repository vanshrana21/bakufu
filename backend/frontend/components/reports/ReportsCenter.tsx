"use client";

import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { ReportConfigurationForm } from "./ReportConfigurationForm";
import { ReportTemplateSelector } from "./ReportTemplateSelector";
import { RecentReportsTable } from "./RecentReportsTable";
import { reportTemplates, type RecentReport, type ReportFormat, type ReportTemplateId } from "./types";

const demoReports: readonly RecentReport[] = [
  { id: "RPT-2026-0091", template: "Monthly Production & Risk Forecast", generated: "12 Sep 2026 · 08:10", requestedBy: "Planning", format: "PDF", status: "Ready", source: "example" },
  { id: "RPT-2026-0089", template: "Ghost Reserve Prospectivity Audit", generated: "10 Sep 2026 · 14:32", requestedBy: "Geology", format: "Excel", status: "Ready", source: "example" },
  { id: "RPT-2026-0088", template: "Regulatory Compliance Summary", generated: "09 Sep 2026 · 11:05", requestedBy: "HSE", format: "PDF", status: "Processing", source: "example" },
  { id: "RPT-2026-0084", template: "Monthly Production & Risk Forecast", generated: "01 Sep 2026 · 09:18", requestedBy: "Executive", format: "CSV", status: "Failed", source: "example" },
];
export function ReportsCenter() {
  const [selected, setSelected] = useState<ReportTemplateId>("production-risk");
  const [reports, setReports] = useState<readonly RecentReport[]>(demoReports);
  const [confirmation, setConfirmation] = useState("");
  const template = reportTemplates.find(item => item.id === selected) ?? reportTemplates[0];
  function generate(format: ReportFormat) { const id = `LOCAL-${String(reports.length + 1).padStart(3, "0")}`; setReports(current => [{ id, template: template.title, generated: "12 Sep 2026 · just now", requestedBy: "Current session", format, status: "Ready", source: "session" }, ...current]); setConfirmation(`${id} added to the local export register. No file was created.`); }
  return <div className="mx-auto max-w-[1800px] px-4 py-6 sm:px-7 sm:py-8"><header className="mb-7 flex flex-wrap items-start justify-between gap-4 border-b pb-6"><div><p className="app-kicker">09 / REPORTS</p><h1 className="app-title">Report Generation &amp; Export Center</h1><p className="app-description">Prepare evidence-led reports for production, Ghost Reserve screening and regulatory review.</p></div><Badge variant="warning">Demo workspace · local generation only</Badge></header>
    <section aria-labelledby="template-heading"><div className="mb-3"><h2 id="template-heading" className="text-base font-semibold">Select report template</h2><p className="mt-1 text-xs text-muted-foreground">Choose the report shape before configuring its date range and output.</p></div><ReportTemplateSelector selected={selected} onSelect={id => { setSelected(id); setConfirmation(""); }} /></section>
    <section aria-labelledby="configure-heading" className="mx-auto mt-8 max-w-4xl"><ReportConfigurationForm templateId={selected} templateName={template.title} onGenerate={generate} /><p role="status" aria-live="polite" className={confirmation ? "mt-3 rounded-md border border-success bg-success-soft p-3 text-sm text-success" : "sr-only"}>{confirmation}</p></section>
    <section aria-labelledby="recent-heading" className="mt-8"><div className="mb-3"><h2 id="recent-heading" className="text-base font-semibold">Recent exports</h2><p className="mt-1 text-xs text-muted-foreground">Previous report requests and their current document-service state.</p></div><RecentReportsTable reports={reports} /></section>
    <p className="mt-6 border-t pt-4 text-xs leading-5 text-muted-foreground">All report rows are illustrative. Screenshots, scores and compliance statuses retain their source caveats; generating an export does not certify the underlying evidence.</p>
  </div>;
}
