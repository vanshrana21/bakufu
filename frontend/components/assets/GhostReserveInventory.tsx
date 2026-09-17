import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Table, TableBody, TableCaption, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

type Reserve = { id: string; name: string; type: "Waste Dump" | "Slag Heap"; volume: string; raw: string; screened: string; assay: "Pending" | "Partial" | "Not sampled" };
const inventory: readonly Reserve[] = [
  { id: "GHOST-SAU-001", name: "Waste dump A", type: "Waste Dump", volume: "186,000 m³", raw: "0.84", screened: "0.84", assay: "Pending" },
  { id: "GHOST-SAU-002", name: "Slag heap B", type: "Slag Heap", volume: "74,500 m³", raw: "0.62", screened: "0.62", assay: "Partial" },
  { id: "GHOST-SAU-003", name: "Waste dump C", type: "Waste Dump", volume: "91,200 m³", raw: "0.76", screened: "—", assay: "Not sampled" },
];

export function GhostReserveInventory() {
  return <Card className="border-primary/60"><CardContent className="p-0"><Table scrollLabel="Ghost Reserve inventory table" className="min-w-[850px]"><TableCaption>Screening indices only. A high score is not measured ore, reserve tonnage or environmental approval. “—” means unavailable, not zero.</TableCaption><TableHeader><TableRow><TableHead>Site ID</TableHead><TableHead>Name</TableHead><TableHead>Type</TableHead><TableHead>Estimated volume</TableHead><TableHead>Raw score</TableHead><TableHead>Screened score</TableHead><TableHead>Assay status</TableHead></TableRow></TableHeader><TableBody>{inventory.map(item => <TableRow key={item.id} data-state={item.id === "GHOST-SAU-001" ? "selected" : undefined}><TableHead scope="row" className="font-mono font-normal text-primary-ink">{item.id}</TableHead><TableCell className="font-medium">{item.name}</TableCell><TableCell><Badge variant="outline">{item.type}</Badge></TableCell><TableCell className="font-mono text-xs">{item.volume}</TableCell><TableCell className="font-mono font-medium" data-kind="model">{item.raw}</TableCell><TableCell className="font-mono font-medium" data-kind="model">{item.screened}</TableCell><TableCell><Badge variant={item.assay === "Pending" ? "warning" : item.assay === "Partial" ? "info" : "secondary"}>{item.assay}</Badge></TableCell></TableRow>)}</TableBody></Table></CardContent></Card>;
}
