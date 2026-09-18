import { CheckCircle2, CircleDot, Clock3 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";

type LogEntry = { date: string; trigger: string; action: string; status: "Completed" | "In review" | "Queued"; detail: string };
const entries: readonly LogEntry[] = [
  { date: "08 Sep 2026", trigger: "Geologist flagged 5 false positives in Sausar Belt", action: "Initiated Stage 9 retraining", status: "Completed", detail: "LOBO evaluation completed · candidate v7 moved to staging" },
  { date: "28 Aug 2026", trigger: "STAC acquisition gap exceeded 72 hours", action: "Paused model refresh", status: "Completed", detail: "Backfill indexed · production model remained unchanged" },
  { date: "18 Aug 2026", trigger: "IMD feed quality warning", action: "Requested data-quality review", status: "In review", detail: "Awaiting source confirmation before using new observations" },
];
const icon = { Completed: CheckCircle2, "In review": Clock3, Queued: CircleDot };
const badge = { Completed: "success", "In review": "warning", Queued: "secondary" } as const;

export function RetrainingLog() {
  return <Card><CardContent className="p-5"><ol className="divide-y divide-border">{entries.map((entry, index) => { const Icon = icon[entry.status]; return <li key={entry.date + entry.trigger} className="grid gap-3 py-4 first:pt-0 last:pb-0 sm:grid-cols-[128px_1fr_auto] sm:items-start"><time className="font-mono text-xs text-muted-foreground">{entry.date}</time><div className="relative pl-7 sm:pl-0"><Icon size={17} className="absolute left-0 top-0.5 text-primary-ink sm:hidden" aria-hidden="true" /><p className="text-sm font-medium">Trigger: {entry.trigger}</p><p className="mt-1 text-sm text-foreground">Action: {entry.action}</p><p className="mt-1 text-xs leading-5 text-muted-foreground">{entry.detail}</p></div><Badge variant={badge[entry.status]}>{entry.status}</Badge></li>; })}</ol></CardContent></Card>;
}
