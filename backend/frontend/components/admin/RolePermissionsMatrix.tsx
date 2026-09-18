import { Check, X } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

const modules = ["Command Center", "Map Explorer", "Feedback Hub", "Pipeline", "Reports", "Admin"] as const;
const roles = ["Admin", "Geologist", "Operator", "Viewer"] as const;

const permissions: Record<(typeof roles)[number], Record<(typeof modules)[number], boolean>> = {
  Admin: { "Command Center": true, "Map Explorer": true, "Feedback Hub": true, Pipeline: true, Reports: true, Admin: true },
  Geologist: { "Command Center": true, "Map Explorer": true, "Feedback Hub": true, Pipeline: true, Reports: true, Admin: false },
  Operator: { "Command Center": true, "Map Explorer": true, "Feedback Hub": true, Pipeline: false, Reports: true, Admin: false },
  Viewer: { "Command Center": true, "Map Explorer": true, "Feedback Hub": false, Pipeline: false, Reports: true, Admin: false },
};

export function RolePermissionsMatrix() {
  return (
    <Card>
      <CardHeader><CardTitle>Role-Based Access Control (RBAC)</CardTitle></CardHeader>
      <CardContent className="overflow-x-auto">
        <table className="min-w-[560px] w-full border-collapse text-left text-sm">
          <thead className="border-b text-xs font-semibold text-muted-foreground">
            <tr>
              <th className="pb-3 font-semibold">Module</th>
              {roles.map((role) => <th key={role} className="pb-3 text-center font-semibold">{role}</th>)}
            </tr>
          </thead>
          <tbody>
            {modules.map((module) => (
              <tr key={module} className="border-b last:border-0">
                <th scope="row" className="py-3 text-left font-normal">{module}</th>
                {roles.map((role) => (
                  <td key={role} className="py-3 text-center" aria-label={`${role} ${permissions[role][module] ? "has access to" : "has no access to"} ${module}`}>
                    {permissions[role][module]
                      ? <Check size={16} className="mx-auto text-success" aria-hidden="true" />
                      : <X size={16} className="mx-auto text-muted-foreground/40" aria-hidden="true" />}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </CardContent>
    </Card>
  );
}
