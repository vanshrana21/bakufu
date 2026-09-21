import { ArrowUpRight, ClipboardCheck } from "lucide-react";
import Link from "next/link";
import type { ActionResponse } from "@/lib/contracts";

export function ActionEvidence({ action, expanded = false }: { action: ActionResponse; expanded?: boolean }) {
  return <section className="action-evidence print-section" aria-labelledby="action-title">
    <div className="action-evidence-heading">
      <h2>Review queue</h2>
      <span className="status-label text-warning"><ClipboardCheck size={14} aria-hidden="true" />{action.review_status === "proposed" ? "Awaiting review" : action.review_status}</span>
    </div>
    <div className="action-evidence-body">
      <div className="action-evidence-meta"><span className="action-rule-id">{action.rule_id}</span><span>Company-wide</span><span>Demo rule · {action.rule_version}</span></div>
      <h3 id="action-title">{action.title}</h3>
      <p className="action-recommendation">{action.recommendation}</p>
      <div className="action-trigger"><span>Trigger</span><span>{action.trigger_condition.summary}</span></div>
      {expanded ? <div className="mt-5 space-y-5">
        <div className="overflow-x-auto"><table className="evidence-table"><caption className="sr-only">Rule trigger observations</caption><thead><tr><th scope="col">Observation</th><th scope="col" className="numeric">Value</th><th scope="col">Operator</th><th scope="col" className="numeric">Threshold</th></tr></thead><tbody>{action.trigger_condition.clauses.map((clause, i) => <tr key={i}><th scope="row">{clause.feature.replaceAll("_", " ")}</th><td className="numeric">{String(clause.observed)}</td><td>{clause.operator}</td><td className="numeric">{String(clause.threshold)}</td></tr>)}</tbody></table></div>
        <dl className="action-review-metadata"><div><dt>Domain validation</dt><dd>{action.domain_validation}</dd></div><div><dt>Reviewer</dt><dd>{action.reviewed_by ?? "Not yet reviewed"}</dd></div></dl>
        <p className="action-evidence-references">Evidence: {action.evidence.map((e) => e.label + " (" + e.reference + ")").join("; ")}.</p>
        <p className="note">Proposed review only. No equipment command, procurement order, or supply commitment has been executed.</p>
      </div> : <Link href="/actions" className="mt-5 inline-flex items-center gap-2 text-sm font-medium text-info underline underline-offset-4">Review trigger and evidence <ArrowUpRight size={15} aria-hidden="true" /></Link>}
    </div>
  </section>;
}
