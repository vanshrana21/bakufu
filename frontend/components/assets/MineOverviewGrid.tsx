import { Activity, Cog, PauseCircle, Wrench } from "lucide-react";
import { Badge, type BadgeProps } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

type MineStatus = "Active" | "Maintenance" | "Idle";
type Mine = { name: string; district: string; status: MineStatus; output: string; equipment: number; plan: string };
const mines: readonly Mine[] = [
  { name: "Tirodi", district: "Balaghat · MP", status: "Active", output: "42,800 t", equipment: 18, plan: "92% of monthly plan" },
  { name: "Dongri Buzurg", district: "Bhandara · MH", status: "Active", output: "36,450 t", equipment: 15, plan: "88% of monthly plan" },
  { name: "Gumgaon", district: "Nagpur · MH", status: "Active", output: "29,160 t", equipment: 12, plan: "96% of monthly plan" },
  { name: "Chikla", district: "Bhandara · MH", status: "Maintenance", output: "18,900 t", equipment: 9, plan: "Crusher maintenance" },
  { name: "Sitasaongi", district: "Balaghat · MP", status: "Active", output: "24,700 t", equipment: 11, plan: "84% of monthly plan" },
  { name: "Munsar", district: "Nagpur · MH", status: "Idle", output: "—", equipment: 3, plan: "Seasonal standby" },
];
const variants: Record<MineStatus, BadgeProps["variant"]> = { Active: "success", Maintenance: "warning", Idle: "secondary" };
const icons = { Active: Activity, Maintenance: Wrench, Idle: PauseCircle };

export function MineOverviewGrid() {
  return <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">{mines.map(mine => { const Icon = icons[mine.status]; return <Card key={mine.name}>
    <CardHeader className="flex-row items-start justify-between gap-3"><div><CardTitle>{mine.name}</CardTitle><p className="mt-1 text-xs text-muted-foreground">{mine.district}</p></div><Badge variant={variants[mine.status]}><Icon size={13} aria-hidden="true" />{mine.status}</Badge></CardHeader>
    <CardContent className="grid grid-cols-2 gap-4"><div><dt className="text-xs text-muted-foreground">Monthly output</dt><dd className="mt-1 font-mono text-lg font-medium tabular-nums">{mine.output}</dd><p className="mt-1 text-xs text-muted-foreground">{mine.plan}</p></div><div><dt className="text-xs text-muted-foreground">Active equipment</dt><dd className="mt-1 font-mono text-lg font-medium tabular-nums">{mine.equipment.toString().padStart(2, "0")}</dd><p className="mt-1 flex items-center gap-1 text-xs text-muted-foreground"><Cog size={12} aria-hidden="true" /> fleet count</p></div></CardContent>
  </Card>; })}</div>;
}
