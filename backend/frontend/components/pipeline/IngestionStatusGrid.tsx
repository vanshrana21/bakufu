import { CheckCircle2, Clock3, Database, Satellite, TriangleAlert } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

type Source = { name: string; kind: "satellite" | "market" | "environment"; status: "Active" | "Warning"; sync: string; records: string; note: string };
const sources: readonly Source[] = [
  { name: "Satellite Imagery (STAC)", kind: "satellite", status: "Active", sync: "12 Sep 2026 · 09:42 UTC", records: "18,420 scenes", note: "Latest Sausar Belt acquisition indexed" },
  { name: "Market Data (BSE)", kind: "market", status: "Active", sync: "12 Sep 2026 · 08:15 UTC", records: "1,284 filings", note: "MOIL filings through Q2 FY26" },
  { name: "Environmental (IMD)", kind: "environment", status: "Warning", sync: "12 Sep 2026 · 05:20 UTC", records: "642 observations", note: "Last sync 4h 22m ago · retry scheduled" },
];
const icons = { satellite: Satellite, market: Database, environment: TriangleAlert };

export function IngestionStatusGrid() {
  return <div className="grid gap-4 md:grid-cols-3">
    {sources.map(source => { const Icon = icons[source.kind]; const active = source.status === "Active"; return <Card key={source.name} className="overflow-hidden">
      <CardHeader className="flex-row items-start justify-between gap-3 border-b bg-surface-raised">
        <CardTitle className="flex items-start gap-3 text-sm"><span className={active ? "grid size-8 place-items-center rounded-md bg-success-soft text-success" : "grid size-8 place-items-center rounded-md bg-warning-soft text-warning"}><Icon size={16} aria-hidden="true" /></span><span>{source.name}</span></CardTitle>
        <Badge variant={active ? "success" : "warning"}>{active ? <CheckCircle2 size={13} aria-hidden="true" /> : <Clock3 size={13} aria-hidden="true" />}{source.status}</Badge>
      </CardHeader>
      <CardContent className="grid grid-cols-2 gap-4 pt-5"><div><dt className="text-xs text-muted-foreground">Last sync</dt><dd className="mt-1 text-xs font-mono text-foreground">{source.sync}</dd></div><div><dt className="text-xs text-muted-foreground">Records</dt><dd className="mt-1 text-sm font-mono font-medium text-foreground">{source.records}</dd></div><p className="col-span-2 border-t pt-3 text-xs leading-5 text-muted-foreground">{source.note}</p></CardContent>
    </Card>; })}
  </div>;
}
