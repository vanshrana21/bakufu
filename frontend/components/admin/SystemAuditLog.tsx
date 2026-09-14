import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

type AuditLog = {
  timestamp: string;
  actor: string;
  action: string;
  ip: string;
  result: "Success" | "Failed";
};

const auditLogs: AuditLog[] = [
  { timestamp: "2026-09-12 09:44:18Z", actor: "anita.rao", action: "Viewed model registry", ip: "10.24.18.42", result: "Success" },
  { timestamp: "2026-09-12 09:12:03Z", actor: "rohan.deshmukh", action: "Submitted annotation", ip: "10.24.21.17", result: "Success" },
  { timestamp: "2026-09-11 17:36:49Z", actor: "unknown", action: "Admin route access attempt", ip: "172.16.4.91", result: "Failed" },
  { timestamp: "2026-09-11 15:08:22Z", actor: "meera.kulkarni", action: "Exported production report", ip: "10.24.19.08", result: "Success" },
  { timestamp: "2026-09-10 11:26:05Z", actor: "system", action: "Model v7 moved to staging", ip: "internal", result: "Success" },
];

export function SystemAuditLog() {
  return (
    <Table scrollLabel="System audit log" className="min-w-[680px]">
      <TableHeader>
        <TableRow>
          <TableHead>Timestamp</TableHead>
          <TableHead>Actor</TableHead>
          <TableHead>Action</TableHead>
          <TableHead>IP Address</TableHead>
          <TableHead>Result</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {auditLogs.map((log) => (
          <TableRow key={`${log.timestamp}-${log.actor}`}>
            <TableHead scope="row" className="whitespace-nowrap font-mono text-xs font-normal text-muted-foreground">{log.timestamp}</TableHead>
            <TableCell>{log.actor}</TableCell>
            <TableCell>{log.action}</TableCell>
            <TableCell className="font-mono text-xs">{log.ip}</TableCell>
            <TableCell><Badge variant={log.result === "Success" ? "default" : "destructive"}>{log.result}</Badge></TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
