import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Table, TableBody, TableCaption, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

type Equipment = { id: string; type: "Excavator" | "Dump Truck" | "Drill"; mine: string; status: "Operational" | "Under repair"; maintenance: string };
const fleet: readonly Equipment[] = [
  { id: "EXC-TIR-07", type: "Excavator", mine: "Tirodi", status: "Operational", maintenance: "18 Sep 2026" },
  { id: "DT-DON-14", type: "Dump Truck", mine: "Dongri Buzurg", status: "Operational", maintenance: "21 Sep 2026" },
  { id: "DRL-GUM-02", type: "Drill", mine: "Gumgaon", status: "Under repair", maintenance: "15 Sep 2026" },
  { id: "EXC-CHI-03", type: "Excavator", mine: "Chikla", status: "Operational", maintenance: "26 Sep 2026" },
  { id: "DT-SIT-09", type: "Dump Truck", mine: "Sitasaongi", status: "Under repair", maintenance: "19 Sep 2026" },
];

export function EquipmentFleetStatus() {
  return <Card><CardContent className="p-0"><Table scrollLabel="Equipment fleet status table" className="min-w-[700px]"><TableCaption>Illustrative fleet snapshot. Maintenance dates are planning metadata and do not represent live telemetry.</TableCaption><TableHeader><TableRow><TableHead>Equipment ID</TableHead><TableHead>Type</TableHead><TableHead>Assigned mine</TableHead><TableHead>Status</TableHead><TableHead>Next maintenance</TableHead></TableRow></TableHeader><TableBody>{fleet.map(item => <TableRow key={item.id}><TableHead scope="row" className="font-mono font-normal">{item.id}</TableHead><TableCell>{item.type}</TableCell><TableCell>{item.mine}</TableCell><TableCell><Badge variant={item.status === "Operational" ? "success" : "warning"}>{item.status}</Badge></TableCell><TableCell className="font-mono text-xs">{item.maintenance}</TableCell></TableRow>)}</TableBody></Table></CardContent></Card>;
}
