import { Badge, type BadgeProps } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Table, TableBody, TableCaption, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

type ModelStatus = "Deployed" | "Staging" | "Archived";
type ModelVersion = { id: string; name: string; metric: string; status: ModelStatus; deployed: string; purpose: string };
const versions: readonly ModelVersion[] = [
  { id: "prospectivity-v6", name: "Prospectivity v6", metric: "LOBO AUC · 0.9034", status: "Deployed", deployed: "08 Sep 2026", purpose: "Sausar Belt screening" },
  { id: "prospectivity-v7-rc1", name: "Prospectivity v7 RC1", metric: "LOBO AUC · 0.9112", status: "Staging", deployed: "—", purpose: "Candidate · review required" },
  { id: "prophet-baseline-v3", name: "Prophet Baseline", metric: "MAPE · 8.7%", status: "Deployed", deployed: "01 Sep 2026", purpose: "Production forecast" },
  { id: "xgb-shortfall-v2", name: "Shortfall XGBoost v2", metric: "LOBO AUC · 0.7810", status: "Archived", deployed: "12 Aug 2026", purpose: "Risk classifier" },
];
const variants: Record<ModelStatus, BadgeProps["variant"]> = { Deployed: "success", Staging: "warning", Archived: "secondary" };

export function ModelVersionRegistry() {
  return <Card><CardContent className="p-0"><Table scrollLabel="MLflow model version registry" className="min-w-[760px]"><TableCaption>Illustrative MLflow registry snapshot. Metrics are model validation metrics, not measured reserve or production claims.</TableCaption><TableHeader><TableRow><TableHead>Version ID</TableHead><TableHead>Model</TableHead><TableHead>Validation metric</TableHead><TableHead>Purpose</TableHead><TableHead>Status</TableHead><TableHead>Deployed</TableHead></TableRow></TableHeader><TableBody>{versions.map(version => <TableRow key={version.id} data-state={version.status === "Deployed" ? "selected" : undefined}><TableHead scope="row" className="font-mono font-normal text-foreground"><span className="whitespace-nowrap">{version.id}</span></TableHead><TableCell className="font-medium">{version.name}</TableCell><TableCell className="font-mono text-xs">{version.metric}</TableCell><TableCell className="text-xs text-muted-foreground">{version.purpose}</TableCell><TableCell><Badge variant={variants[version.status]}>{version.status}</Badge></TableCell><TableCell className="whitespace-nowrap text-xs text-muted-foreground">{version.deployed}</TableCell></TableRow>)}</TableBody></Table></CardContent></Card>;
}
