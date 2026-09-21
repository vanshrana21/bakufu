"use client";
import Link from "next/link";
import { useState } from "react";
import { ArrowUpRight, ArrowRight } from "lucide-react";
import type { ActionResponse } from "@/lib/contracts";
import type { RegisterRow } from "@/lib/api/recommendations";

const FILTERS = ["all", "proposed", "reviewed"] as const;
const label = (value: (typeof FILTERS)[number]) => value === "all" ? "All" : value === "proposed" ? "Proposed" : "Reviewed";

export function ReviewRegister({ rows: allRows, selectedId, onSelect, message }: {
  rows: readonly RegisterRow[];
  selectedId?: string;
  onSelect?: (action: ActionResponse) => void;
  /** The engine's own explanation for an empty set (e.g. risk below the floor).
   * Without it an empty register is indistinguishable from a failed load. */
  message?: string | null;
}) {
  const [filter, setFilter] = useState<(typeof FILTERS)[number]>("all");
  const rows = allRows.filter(({ action }) => filter === "all" || action.review_status === filter);
  return <section className="review-register operations-register print-section" aria-label="Review register">
    <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
      <div className="flex flex-wrap items-baseline gap-x-5 gap-y-2"><h2 className="register-heading">Review register</h2><p className="text-xs text-metadata">Proposed corrective actions · demonstration rules · human review required</p></div>
      <div className="register-filters no-print" role="group" aria-label="Filter reviews">{FILTERS.map((value) => <button key={value} type="button" className="register-filter" onClick={() => setFilter(value)} aria-pressed={filter === value}>{label(value)} ({allRows.filter(({ action }) => value === "all" || action.review_status === value).length})</button>)}</div>
    </div>
    <div className="overflow-x-auto"><table className="evidence-table">
      <caption className="sr-only">Synthetic review register. Owners and target dates are illustrative, not assigned commitments.</caption>
      <thead><tr><th scope="col">#</th><th scope="col">Priority</th><th scope="col">Action / recommendation</th><th scope="col">Evidence</th><th scope="col">Proposed owner</th><th scope="col">Target date</th><th scope="col">Status</th></tr></thead>
      <tbody>{rows.map(({ action, priority, owner, target_date }, i) => <tr key={action.action_id} data-selected={selectedId === action.action_id ? "true" : undefined}>
        <td className="numeric text-metadata">{String(i + 1).padStart(2, "0")}</td>
        <td className="whitespace-nowrap"><span aria-hidden="true" className={priority === "High" ? "text-critical" : "text-warning"}>●</span> {priority}</td>
        <th scope="row">{onSelect
          ? <button type="button" className="register-action-link" onClick={() => onSelect(action)} aria-pressed={selectedId === action.action_id} aria-controls="selected-action-evidence">{action.title}<ArrowRight size={13} aria-hidden="true" /></button>
          : <Link href={"/actions?review=" + action.action_id} className="register-action-link">{action.title}<ArrowUpRight size={13} aria-hidden="true" /></Link>}</th>
        <td className="max-w-64 text-metadata">{action.evidence[0]?.label}</td><td>{owner ?? <span className="text-metadata">Not assigned</span>}</td><td className="whitespace-nowrap numeric">{target_date ?? <span className="text-metadata">—</span>}</td><td><span className="review-status">{action.review_status}</span></td>
      </tr>)}</tbody>
    </table>{rows.length === 0 && <p role="status" className="py-8 text-center text-sm text-metadata">{filter === "all" && message ? message : "No reviewed actions. The demonstration does not fabricate approvals."}</p>}</div>
    <p className="mt-3 text-[11px] text-metadata">Synthetic evidence, owners and dates. No equipment command, procurement order or supply commitment has been executed.</p>
  </section>;
}
