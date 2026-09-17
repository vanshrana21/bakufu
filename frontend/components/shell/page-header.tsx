import type { ReactNode } from "react";

/** Shared title rhythm for every workspace module. */
export function PageHeader({ kicker, title, description, status, actions }: {
  /** The sheet reference, e.g. "01 / COMMAND", matching the other pages. */
  kicker?: string;
  title: string;
  description: string;
  status?: ReactNode;
  actions?: ReactNode;
}) {
  return <header className="module-header">
    <div className="module-heading">{kicker && <p className="app-kicker">{kicker}</p>}<h1>{title}</h1><p>{description}</p></div>
    {(status || actions) && <div className="module-header-tools">
      {status && <div className="module-status">{status}</div>}
      {actions && <div className="module-actions">{actions}</div>}
    </div>}
  </header>;
}
