"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import { FileDown, LoaderCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Select } from "@/components/ui/select";
import type { ReportFormat, ReportTemplateId } from "./types";

const mines = ["All operating mines", "Tirodi", "Dongri Buzurg", "Gumgaon", "Chikla", "Sitasaongi", "Munsar"];
export function ReportConfigurationForm({ templateId, templateName, onGenerate }: { templateId: ReportTemplateId; templateName: string; onGenerate: (format: ReportFormat) => void }) {
  const [format, setFormat] = useState<ReportFormat>("PDF");
  const [generating, setGenerating] = useState(false);
  const timeoutRef = useRef<number | null>(null);
  useEffect(() => () => { if (timeoutRef.current !== null) window.clearTimeout(timeoutRef.current); }, []);
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setGenerating(true);
    if (timeoutRef.current !== null) window.clearTimeout(timeoutRef.current);
    timeoutRef.current = window.setTimeout(() => { setGenerating(false); onGenerate(format); }, 700);
  }
  return <Card><CardHeader><CardTitle>Configure &amp; generate</CardTitle><CardDescription>{templateName}</CardDescription></CardHeader><CardContent><form onSubmit={submit} className="space-y-5">
    <div className="grid gap-4 sm:grid-cols-2"><div><label htmlFor="report-start" className="mb-1.5 block text-sm font-medium">Start date</label><input id="report-start" name="start" type="date" defaultValue="2026-08-01" required className="ui-control h-10 w-full rounded-md border border-input bg-surface px-3 text-sm text-foreground" /></div><div><label htmlFor="report-end" className="mb-1.5 block text-sm font-medium">End date</label><input id="report-end" name="end" type="date" defaultValue="2026-09-12" required className="ui-control h-10 w-full rounded-md border border-input bg-surface px-3 text-sm text-foreground" /></div></div>
    <div><label htmlFor="report-mines" className="mb-1.5 block text-sm font-medium">Target mines</label><Select id="report-mines" name="mines" multiple defaultValue={mines[0] ? [mines[0]] : []} className="h-auto min-h-24 py-2">{mines.map(mine => <option key={mine} value={mine}>{mine}</option>)}</Select><p className="mt-1.5 text-xs text-muted-foreground">Hold Ctrl/Cmd to select multiple sites. “All operating mines” is illustrative.</p></div>
    <fieldset><legend className="mb-2 text-sm font-medium">Output format</legend><div className="grid gap-2 sm:grid-cols-3">{(["PDF", "Excel", "CSV"] as const).map(value => <label key={value} className="flex cursor-pointer items-center gap-2 rounded-md border border-border px-3 py-2.5 text-sm hover:bg-muted"><input type="radio" name="format" value={value} checked={format === value} onChange={() => setFormat(value)} className="accent-[var(--primary)]" />{value}</label>)}</div></fieldset>
    <div className="flex flex-wrap items-center gap-3 border-t pt-4"><Button type="submit" disabled={generating}>{generating ? <><LoaderCircle size={15} className="animate-spin" aria-hidden="true" />Generating…</> : <><FileDown size={15} aria-hidden="true" />Generate report</>}</Button><span className="text-xs text-muted-foreground">Demo generation only · no file is downloaded.</span></div>
  </form></CardContent></Card>;
}
