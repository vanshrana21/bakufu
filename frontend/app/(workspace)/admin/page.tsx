import { RolePermissionsMatrix } from "@/components/admin/RolePermissionsMatrix";
import { SystemAuditLog } from "@/components/admin/SystemAuditLog";
import { UserManagementTable } from "@/components/admin/UserManagementTable";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function AdminPage() {
  return (
    <div className="mx-auto max-w-[1800px] px-4 py-6 sm:px-7 sm:py-8">
      <header className="mb-7 border-b pb-6">
        <p className="app-kicker">10 / ADMIN</p>
        <h1 className="app-title">Administration &amp; Security</h1>
        <p className="app-description">Manage users, role-based access, and the security audit trail for the enterprise workspace.</p>
      </header>
      <div className="grid gap-6 lg:grid-cols-2">
        <Card className="lg:col-span-2">
          <CardHeader><CardTitle>User Management</CardTitle></CardHeader>
          <CardContent className="p-0"><UserManagementTable /></CardContent>
        </Card>
        <RolePermissionsMatrix />
        <Card>
          <CardHeader><CardTitle>System Audit Log</CardTitle></CardHeader>
          <CardContent className="p-0"><SystemAuditLog /></CardContent>
          <footer className="border-t bg-surface-raised px-5 py-3 text-xs text-muted-foreground">Audit events are retained for 365 days.</footer>
        </Card>
      </div>
    </div>
  );
}
