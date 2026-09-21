import { Badge, type BadgeProps } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Table, TableBody, TableCaption, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

type PermitStatus = "Active" | "Expiring" | "Expired";
type Permit = { id: string; type: string; authority: string; issued: string; expiry: string; status: PermitStatus };
const permits: readonly Permit[] = [
  { id: "FC-MP-SAU-2024-118", type: "Forest Clearance", authority: "MoEFCC · MP RO", issued: "14 Mar 2024", expiry: "30 Nov 2026", status: "Expiring" },
  { id: "EC-MOIL-2025-042", type: "Environmental Clearance", authority: "MoEFCC", issued: "06 Jun 2025", expiry: "06 Jun 2030", status: "Active" },
  { id: "DGMS-TIR-2026-009", type: "DGMS Safety", authority: "DGMS Nagpur", issued: "12 Jan 2026", expiry: "11 Jan 2027", status: "Active" },
  { id: "CTO-MH-DON-2023-77", type: "Consent to Operate", authority: "MPCB", issued: "22 Aug 2023", expiry: "21 Aug 2026", status: "Expired" },
  { id: "WTR-BAL-2025-031", type: "Water abstraction", authority: "CGWA", issued: "03 Dec 2025", expiry: "02 Dec 2026", status: "Expiring" },
  { id: "BLD-SIT-2026-014", type: "Mine plan approval", authority: "IBM Nagpur", issued: "18 Feb 2026", expiry: "17 Feb 2029", status: "Active" },
];
const variants: Record<PermitStatus, BadgeProps["variant"]> = { Active: "success", Expiring: "warning", Expired: "destructive" };

export function PermitRegistryTable() {
  return <Card><CardContent className="p-0"><Table scrollLabel="Permit and clearance registry" className="min-w-[900px]"><TableCaption>Illustrative registry snapshot. Dates and statuses require confirmation against the authoritative permit record before action.</TableCaption><TableHeader><TableRow><TableHead>Permit ID</TableHead><TableHead>Permit type</TableHead><TableHead>Issuing authority</TableHead><TableHead>Issue date</TableHead><TableHead>Expiry date</TableHead><TableHead>Status</TableHead></TableRow></TableHeader><TableBody>{permits.map(permit => <TableRow key={permit.id} data-state={permit.status === "Expiring" ? "selected" : undefined}><TableHead scope="row" className="font-mono font-normal text-primary-ink">{permit.id}</TableHead><TableCell className="font-medium">{permit.type}</TableCell><TableCell className="text-xs text-muted-foreground">{permit.authority}</TableCell><TableCell className="whitespace-nowrap font-mono text-xs">{permit.issued}</TableCell><TableCell className="whitespace-nowrap font-mono text-xs">{permit.expiry}</TableCell><TableCell><Badge variant={variants[permit.status]}>{permit.status}</Badge></TableCell></TableRow>)}</TableBody></Table></CardContent></Card>;
}
