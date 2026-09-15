"use client";

import Link from "next/link";
import { useState } from "react";
import { ArrowUpRight, Check } from "lucide-react";
import type { ActionResponse } from "@/lib/contracts";
import type { RegisterRow } from "@/lib/api/recommendations";
import s from "./briefing.module.css";

const FILTERS = ["all", "proposed", "reviewed"] as const;
type Filter = (typeof FILTERS)[number];
const filterLabel = (value: Filter) => value === "all" ? "All" : value === "proposed" ? "Proposed" : "Reviewed";

/** Block 4: the review register and the demonstration rules beside it. */
export function BriefingHumans({ rows: allRows, message, demoRules }: {
  rows: readonly RegisterRow[];
  /** The engine's own reason for an empty set, so it never reads as a failed load. */
  message: string | null;
  demoRules: readonly ActionResponse[];
}) {
  const [filter, setFilter] = useState<Filter>("all");
  const rows = allRows.filter(({ action }) => filter === "all" || action.review_status === filter);
  const count = (value: Filter) => allRows.filter(({ action }) => value === "all" || action.review_status === value).length;

  return <div className={s.humanGrid}>
    <section className={`print-section ${s.register}`} aria-label="Review register">
      <div className={s.registerBar}>
        <p className={s.registerTitle}>Review register</p>
        <div className={`no-print ${s.filters}`} role="group" aria-label="Filter reviews">
          {FILTERS.map((value) => <button key={value} type="button" className={s.filter} onClick={() => setFilter(value)} aria-pressed={filter === value}>
            {filterLabel(value)} <span>{count(value)}</span>
          </button>)}
        </div>
      </div>
      {rows.length > 0
        ? <div className={s.tableScroll}>
          <table className={s.registerTable}>
            <caption className="sr-only">Review register. Owners and target dates are illustrative, not assigned commitments.</caption>
            <thead><tr><th scope="col">Priority</th><th scope="col">Action</th><th scope="col">Evidence</th><th scope="col">Owner</th><th scope="col">Target date</th><th scope="col">Status</th></tr></thead>
            <tbody>{rows.map(({ action, priority, owner, target_date }) => <tr key={action.action_id}>
              <td className={s.nowrap}>{priority}</td>
              <th scope="row"><Link href={"/actions?review=" + action.action_id} className="register-action-link">{action.title}<ArrowUpRight size={13} aria-hidden="true" /></Link></th>
              <td className={s.muted}>{action.evidence[0]?.label}</td>
              <td>{owner ?? <span className={s.muted}>Not assigned</span>}</td>
              <td className={s.nowrap}>{target_date ?? <span className={s.muted}>—</span>}</td>
              <td><span className={s.statusTag}>{action.review_status}</span></td>
            </tr>)}</tbody>
          </table>
        </div>
        : <div role="status" className={s.empty}>
          {filter === "all"
            ? <>
              <span className={s.emptyMark} aria-hidden="true">
                <svg viewBox="0 0 64 64"><circle cx="32" cy="32" r="28" pathLength={1} /></svg>
                <Check size={26} strokeWidth={2.5} />
              </span>
              <p className={s.emptyLine}>Nothing needs a decision right now.</p>
              {message && <p className={s.emptyReason}>{message}</p>}
            </>
            : <p className={s.emptyLine} data-size="small">No reviewed actions. The demonstration does not fabricate approvals.</p>}
        </div>}
      <p className={s.footnote}>Synthetic evidence, owners and dates. No equipment command, procurement order or supply commitment has been executed.</p>
    </section>

    <div className={s.demoColumn}>
      {demoRules.map((action) => {
        const inRegister = allRows.some((row) => row.action.action_id === action.action_id);
        return <article key={action.action_id} className={`print-section ${s.demo}`} aria-labelledby={`${action.action_id}-title`}>
          <span className={s.demoTag}>DEMONSTRATION — not real yet</span>
          <p className={s.demoMeta}>
            <span>{action.rule_id}</span><span>Company-wide</span><span>Demo rule · {action.rule_version}</span>
          </p>
          <h3 id={`${action.action_id}-title`} className={s.demoTitle}>{action.title}</h3>
          <p className={s.demoText}>{action.recommendation}</p>
          <p className={s.demoTrigger}><span>Trigger</span>{action.trigger_condition.summary}</p>
          <p className={s.demoFoot}>
            <span className={s.statusTag}>{inRegister ? action.review_status : action.rule_version}</span>
            <Link href="/actions" className={s.demoLink}>Review trigger and evidence <ArrowUpRight size={15} aria-hidden="true" /></Link>
          </p>
        </article>;
      })}
    </div>
  </div>;
}
