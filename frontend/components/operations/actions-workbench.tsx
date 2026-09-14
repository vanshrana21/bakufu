"use client";
import { useRef, useState } from "react";
import { ClipboardCheck, ArrowDown, ShieldCheck } from "lucide-react";
import type { RegisterRow } from "@/lib/api/recommendations";
import { ActionEvidence } from "./action-evidence";
import { ReviewRegister } from "./review-register";

export function ActionsWorkbench({ rows, initialId, message }: { rows: readonly RegisterRow[]; initialId?: string; message?: string | null }) {
  const initial = rows.find(({ action }) => action.action_id === initialId);
  const [selected, setSelected] = useState(initial ?? rows[0]);
  const evidenceRef = useRef<HTMLDivElement>(null);
  const pending = rows.filter(({ action }) => action.review_status === "proposed").length;
  if (!selected) return <p role="status" className="note">{message ?? "No proposed actions were returned. Nothing has been withheld."}</p>;
  return <>
    {initialId && !initial && <p role="status" className="note mb-4">That review ID was not found. Showing the first demonstration rule; no decision has been recorded.</p>}
    <div className="actions-layout">
      <aside className="instrument-rail">
        <div className="instrument-rail-label"><ClipboardCheck size={17} aria-hidden="true" /><h2>Review docket</h2></div>
        <div className="docket-count"><strong>{String(pending).padStart(2, "0")}</strong><span>Actions awaiting review</span></div>
        <p className="docket-copy">Each recommendation is a proposal. Inspect its observed trigger before considering any operational change.</p>
        <dl className="instrument-metadata">
          <div><dt>Selected rule</dt><dd>{selected.action.rule_id}</dd></div>
          <div><dt>Priority</dt><dd>{selected.priority}</dd></div>
          <div><dt>Proposed owner</dt><dd>{selected.owner ?? "Not assigned"}</dd></div>
          <div><dt>Illustrative target</dt><dd>{selected.target_date ?? "—"}</dd></div>
          <div><dt>Review status</dt><dd><span className="docket-status"><ClipboardCheck size={12} aria-hidden="true" />{selected.action.review_status}</span></dd></div>
        </dl>
        <p className="docket-guide"><ArrowDown size={14} aria-hidden="true" /> Choose another rule in the register below.</p>
      </aside>
      <div id="selected-action-evidence" ref={evidenceRef} tabIndex={-1} aria-live="polite" aria-atomic="false" className="action-evidence-target min-w-0"><ActionEvidence action={selected.action} expanded /></div>
      <aside className="decision-protocol">
        <div className="decision-protocol-heading"><span>Decision protocol</span><ShieldCheck size={18} aria-hidden="true" /></div>
        <h2>Evidence before action.</h2>
        <ol className="protocol-steps">
          <li><span>01</span><div><strong>Verify the observation</strong><p>Confirm source observations and the forecast issue date.</p></div></li>
          <li><span>02</span><div><strong>Validate the rule</strong><p>Check its causal reasoning and operational context with a domain expert.</p></div></li>
          <li><span>03</span><div><strong>Record the decision</strong><p>A named reviewer must approve the next step in the live system.</p></div></li>
        </ol>
        <p className="decision-protocol-note">Approval persistence and operational execution are not connected. Owners and dates are illustrative; no assignments have been sent.</p>
      </aside>
    </div>
    <ReviewRegister rows={rows} message={message} selectedId={selected.action.action_id} onSelect={(action) => {
      const row = rows.find((entry) => entry.action.action_id === action.action_id);
      if (row) {
        setSelected(row);
        // A register row can be below the inspector, especially on a phone.
        // Bring the selected evidence into view instead of silently changing it off-screen.
        requestAnimationFrame(() => {
          const evidence = evidenceRef.current;
          if (!evidence) return;
          evidence.focus({ preventScroll: true });
          evidence.scrollIntoView({ block: "start", behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
        });
      }
    }} />
  </>;
}
