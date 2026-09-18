import { Download } from "lucide-react";
import { Badge, type BadgeProps } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Table, TableBody, TableCaption, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import type { RecentReport } from "./types";

const variants: Record<RecentReport["status"], BadgeProps["variant"]> = { Ready: "success", Processing: "warning", Failed: "destructive" };
export function RecentReportsTable({ reports }: { reports: readonly RecentReport[] }) {
  return <Card><CardContent className="p-0"><Table scrollLabel="Recent reports table" className="min-w-[850px]"><TableCaption>Illustrative export history. Download controls are inactive until a real report service is connected.</TableCaption><TableHeader><TableRow><TableHead>Report ID</TableHead><TableHead>Template</TableHead><TableHead>Generated</TableHead><TableHead>Requested by</TableHead><TableHead>Format</TableHead><TableHead>Status</TableHead><TableHead className="text-right">Action</TableHead></TableRow></TableHeader><TableBody>{reports.map(report => <TableRow key={report.id}><TableHead scope="row" className="font-mono font-normal text-primary-ink">{report.id}<span className="mt-1 block font-sans text-xs text-muted-foreground">{report.source === "example" ? "Example" : "Local only"}</span></TableHead><TableCell className="min-w-[210px] font-medium">{report.template}</TableCell><TableCell className="whitespace-nowrap font-mono text-xs">{report.generated}</TableCell><TableCell className="text-xs text-muted-foreground">{report.requestedBy}</TableCell><TableCell><Badge variant="outline">{report.format}</Badge></TableCell><TableCell><Badge variant={variants[report.status]}>{report.status}</Badge></TableCell><TableCell className="text-right"><Button type="button" variant="ghost" size="icon" disabled aria-label={`Download ${report.id}`} title="Download connects in a later integration phase"><Download size={16} aria-hidden="true" /></Button></TableCell></TableRow>)}</TableBody></Table></CardContent></Card>;
}
