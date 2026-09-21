import { AlertTriangle, CheckCircle2, ClipboardCheck } from "lucide-react";
import { Badge, type BadgeProps } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

type Summary = { title: string; count: string; detail: string; status: string; variant: BadgeProps["variant"]; icon: typeof CheckCircle2 };
const summaries: readonly Summary[] = [
  { title: "Active permits", count: "12", detail: "Across operating sites", status: "Healthy", variant: "success", icon: CheckCircle2 },
  { title: "Expiring soon (< 90 days)", count: "03", detail: "Renewal review required", status: "Attention", variant: "warning", icon: AlertTriangle },
  { title: "Open audit findings", count: "01", detail: "Owner response pending", status: "Critical", variant: "destructive", icon: ClipboardCheck },
];

export function ComplianceOverviewGrid() {
  return <div className="grid gap-4 md:grid-cols-3">{summaries.map(summary => { const Icon = summary.icon; return <Card key={summary.title}><CardHeader className="flex-row items-start justify-between gap-3"><CardTitle className="text-sm">{summary.title}</CardTitle><Badge variant={summary.variant}><Icon size={13} aria-hidden="true" />{summary.status}</Badge></CardHeader><CardContent><p className="font-mono text-3xl font-medium tracking-tight tabular-nums">{summary.count}</p><p className="mt-2 text-xs text-muted-foreground">{summary.detail}</p></CardContent></Card>; })}</div>;
}
