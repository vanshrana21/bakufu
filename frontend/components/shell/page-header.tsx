import type { ReactNode } from "react";

/** Shared title rhythm for every workspace module. */
export function PageHeader({ title, description, status, actions }: {
  title: string;
  description: string;
  status?: ReactNode;
  actions?: ReactNode;
}) {
  return <header className="module-header">
    <div className="module-heading"><h1>{title}</h1><p>{description}</p></div>
    {(status || actions) && <div className="module-header-tools">
      {status && <div className="module-status">{status}</div>}
      {actions && <div className="module-actions">{actions}</div>}
    </div>}
  </header>;
}
