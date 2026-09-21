import { Badge, type BadgeProps } from "@/components/ui/badge";
import { Table, TableBody, TableCaption, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import type { Annotation, Severity } from "./types";

const severityVariant: Record<Severity, BadgeProps["variant"]> = { Low: "secondary", Medium: "warning", High: "destructive" };
const dateFormat = new Intl.DateTimeFormat("en-GB", { day: "2-digit", month: "short", year: "numeric", timeZone: "UTC" });

export function PendingAnnotationsTable({ annotations }: { annotations: readonly Annotation[] }) {
  const pending = annotations.filter(annotation => annotation.status === "Pending").length;
  return <section aria-labelledby="annotations-heading" className="min-w-0">
    <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
      <div><h2 id="annotations-heading" className="text-base font-semibold">Annotation register</h2><p className="mt-1 text-xs text-muted-foreground">Synthetic examples and entries from this session.</p></div>
      <Badge variant="outline">{pending} pending · {annotations.length} total</Badge>
    </div>
    <Table scrollLabel="Annotation register table" className="min-w-[680px]">
      <TableCaption>Dates shown in UTC. “Reviewed” is an illustrative workflow status, not confirmation of ore, an approved label or completed retraining.</TableCaption>
      <TableHeader><TableRow>{["ID", "Date", "Site name", "Type", "Severity", "Status"].map(label => <TableHead key={label}>{label}</TableHead>)}</TableRow></TableHeader>
      <TableBody>
        {annotations.length === 0 && <TableRow><TableCell colSpan={6} className="py-8 text-center text-muted-foreground">No annotations in this session.</TableCell></TableRow>}
        {annotations.map(annotation => <TableRow key={annotation.id}>
          <TableHead scope="row" className="font-mono font-normal text-foreground"><span className="whitespace-nowrap">{annotation.id}</span><span className="mt-1 block font-sans text-xs text-muted-foreground">{annotation.source === "example" ? "Example" : "Local only"}</span></TableHead>
          <TableCell className="whitespace-nowrap text-xs"><time dateTime={annotation.createdAt}>{dateFormat.format(new Date(annotation.createdAt))}</time></TableCell>
          <TableCell className="min-w-[180px] max-w-64"><span className="block text-sm">{annotation.siteName ?? "Name unavailable"}</span><span className="mt-1 block break-all font-mono text-xs text-muted-foreground">{annotation.siteId}</span>
            <details className="mt-2 text-xs"><summary className="cursor-pointer text-primary-ink">View notes<span className="sr-only"> for {annotation.id}</span></summary><p className="mt-2 whitespace-pre-wrap break-words leading-5 text-muted-foreground">{annotation.notes}</p></details>
          </TableCell>
          <TableCell className="text-xs">{annotation.type}</TableCell>
          <TableCell><Badge variant={severityVariant[annotation.severity]}>{annotation.severity}</Badge></TableCell>
          <TableCell><Badge variant={annotation.status === "Pending" ? "warning" : "secondary"}>{annotation.status}</Badge></TableCell>
        </TableRow>)}
      </TableBody>
    </Table>
  </section>;
}
