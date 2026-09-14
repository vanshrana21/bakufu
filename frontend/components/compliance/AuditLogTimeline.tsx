import { AlertTriangle, CheckCircle2, FileCheck2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";

type Event = { date: string; title: string; detail: string; status: "Completed" | "Submitted" | "Open finding"; icon: typeof CheckCircle2 };
const events: readonly Event[] = [
  { date: "12 Sep 2026 · 11:10 UTC", title: "Site inspection at Tirodi Mine", detail: "Inspection checklist closed; evidence package awaiting archive confirmation.", status: "Completed", icon: CheckCircle2 },
  { date: "08 Sep 2026 · 16:40 UTC", title: "MoEFCC quarterly report submitted", detail: "Illustrative submission record linked to the September reporting cycle.", status: "Submitted", icon: FileCheck2 },
  { date: "04 Sep 2026 · 09:25 UTC", title: "Safety audit finding: haul-road drainage blocked", detail: "Owner response and remediation evidence are still required.", status: "Open finding", icon: AlertTriangle },
];
const variants = { Completed: "success", Submitted: "info", "Open finding": "destructive" } as const;

export function AuditLogTimeline() {
  return <Card><CardContent className="p-5"><ol className="relative ml-2 border-l border-border">{events.map(event => { const Icon = event.icon; return <li key={event.date + event.title} className="relative pb-7 pl-7 last:pb-0"><span className="absolute -left-[13px] top-0 grid size-6 place-items-center rounded-full border border-border bg-card text-muted-foreground"><Icon size={13} aria-hidden="true" /></span><div className="flex flex-wrap items-start justify-between gap-3"><div><time className="font-mono text-xs text-muted-foreground">{event.date}</time><h3 className="mt-1 text-sm font-medium">{event.title}</h3><p className="mt-1 max-w-3xl text-xs leading-5 text-muted-foreground">{event.detail}</p></div><Badge variant={variants[event.status]}>{event.status}</Badge></div></li>; })}</ol></CardContent></Card>;
}
