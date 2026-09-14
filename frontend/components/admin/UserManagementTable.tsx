import { MoreHorizontal } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

type User = {
  id: string;
  name: string;
  email: string;
  role: "Admin" | "Geologist" | "Operator" | "Viewer";
  status: "Active" | "Invited";
};

const users: User[] = [
  { id: "USR-0001", name: "Anita Rao", email: "anita.rao@moil.example", role: "Admin", status: "Active" },
  { id: "USR-0002", name: "Rohan Deshmukh", email: "rohan.deshmukh@moil.example", role: "Geologist", status: "Active" },
  { id: "USR-0003", name: "Meera Kulkarni", email: "meera.kulkarni@moil.example", role: "Operator", status: "Active" },
  { id: "USR-0004", name: "Vikram Singh", email: "vikram.singh@moil.example", role: "Viewer", status: "Invited" },
  { id: "USR-0005", name: "Neha Patil", email: "neha.patil@moil.example", role: "Geologist", status: "Active" },
];

const roleColors: Record<User["role"], string> = {
  Admin: "bg-[var(--primary)]/10 text-[var(--primary)] border border-[var(--primary)]/20",
  Geologist: "bg-[var(--oxide)]/10 text-[var(--oxide)] border border-[var(--oxide)]/20",
  Operator: "border-[var(--border-strong)] bg-transparent text-foreground",
  Viewer: "border-transparent bg-muted text-muted-foreground",
};

export function UserManagementTable() {
  return (
    <Table scrollLabel="User management table" className="min-w-[760px]">
      <TableHeader>
        <TableRow>
          <TableHead>User ID</TableHead>
          <TableHead>Name</TableHead>
          <TableHead>Email</TableHead>
          <TableHead>Role</TableHead>
          <TableHead>Status</TableHead>
          <TableHead className="text-right">Actions</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {users.map((user) => (
          <TableRow key={user.id}>
            <TableHead scope="row" className="font-mono font-normal">{user.id}</TableHead>
            <TableCell className="font-medium">{user.name}</TableCell>
            <TableCell className="text-sm text-muted-foreground">{user.email}</TableCell>
            <TableCell><Badge className={roleColors[user.role]}>{user.role}</Badge></TableCell>
            <TableCell><Badge variant={user.status === "Active" ? "success" : "warning"}>{user.status}</Badge></TableCell>
            <TableCell className="text-right">
              <Button type="button" variant="ghost" size="icon" disabled aria-disabled="true" title="Requires backend integration" aria-label={`Actions for ${user.name}`}>
                <MoreHorizontal size={16} aria-hidden="true" />
              </Button>
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
