import { AlertTriangle, FlaskConical } from "lucide-react";
import type { VitalSign } from "@/lib/api/dashboard";

/** Four operational values with their uncertainty qualifiers.
 *
 * Values are supplied by the page, which decides live vs fixture. A tile whose
 * backing component failed renders an em dash — a missing number must never be
 * shown as zero, and zero here would read as "production stopped".
 */
export function VitalSigns({ signs, degraded = [], syntheticNote = null, origin }: {
  signs: readonly VitalSign[];
  degraded?: readonly string[];
  syntheticNote?: string | null;
  origin: "live" | "fixture";
}) {
  return <>
    {syntheticNote && <p role="status" className="note mb-3 flex items-start gap-2">
      <AlertTriangle size={15} className="mt-0.5 shrink-0" aria-hidden="true" />
      <span><strong>Synthetic artifacts.</strong> {syntheticNote}</span>
    </p>}
    {degraded.length > 0 && <p role="status" className="note mb-3">
      Degraded components: {degraded.join(", ")}. Their values are withheld rather than substituted.
    </p>}
    {origin === "fixture" && <p className="mb-3 flex items-center gap-2 text-[11px] text-metadata">
      <FlaskConical size={13} aria-hidden="true" /> Demonstration fixtures · no API configured
    </p>}
    <dl className="vital-signs" aria-label="Four vital signs">
      {signs.map((sign) => <div key={sign.label} className="vital-sign" data-unavailable={sign.unavailable || undefined}>
        <dt>{sign.label}</dt>
        <dd><span data-testid={sign.testId}>{sign.value}</span>{sign.unit ? <small> {sign.unit}</small> : null}</dd>
        <p>{sign.note}</p>
      </div>)}
    </dl>
  </>;
}
