"use client";

import { BarChart3, MapPinned, ShieldCheck } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { reportTemplates, type ReportTemplateId } from "./types";

const icons = { chart: BarChart3, map: MapPinned, shield: ShieldCheck } as const;
export function ReportTemplateSelector({ selected, onSelect }: { selected: ReportTemplateId; onSelect: (id: ReportTemplateId) => void }) {
  return <div className="grid gap-4 md:grid-cols-3">{reportTemplates.map(template => { const Icon = icons[template.icon]; const active = template.id === selected; return <button key={template.id} type="button" aria-pressed={active} onClick={() => onSelect(template.id)} className="text-left">
    <Card className={cn("h-full transition-colors hover:border-primary-ink hover:bg-primary-soft", active && "border-primary bg-primary-soft") }><CardHeader className="flex-row items-start gap-3"><span className={cn("grid size-9 place-items-center rounded-md border bg-surface-raised text-muted-foreground", active && "border-primary bg-primary text-primary-foreground")}><Icon size={17} aria-hidden="true" /></span><CardTitle className="pt-1 text-sm leading-5">{template.title}</CardTitle></CardHeader><CardContent><p className="text-xs leading-5 text-muted-foreground">{template.description}</p><span className="mt-4 block text-xs font-medium text-primary-ink">{active ? "Selected template" : "Select template"}</span></CardContent></Card>
  </button>; })}</div>;
}
