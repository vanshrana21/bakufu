import { AlertTriangle, CircleHelp } from "lucide-react";
import type { RiskResponse } from "@/lib/contracts";

/** Presentation policy, NOT model-derived severity thresholds. Displayed in UI. */
const BANDS = [
  { limit: 30, level: "Low", tone: "text-success", stroke: "var(--success)" },
  { limit: 60, level: "Review", tone: "text-warning", stroke: "var(--warning)" },
  { limit: Infinity, level: "Critical", tone: "text-critical", stroke: "var(--critical)" },
] as const;

function Donut({ percentage, stroke, level, calibration }: { percentage: number; stroke: string; level: string; calibration: string }) {
  return <div className="risk-donut" role="meter" aria-label="Shortfall probability" aria-valuemin={0} aria-valuemax={100} aria-valuenow={percentage}
    aria-valuetext={`${Math.round(percentage)} percent. ${level}. ${calibration}.`}>
    {/* The arc carries the same band color as the written level, so severity is
        never conveyed by the text label alone. */}
    <svg viewBox="0 0 120 120" aria-hidden="true">
      <circle cx="60" cy="60" r="48" fill="none" stroke="var(--muted)" strokeWidth="11" />
      <circle cx="60" cy="60" r="48" fill="none" stroke={stroke} strokeWidth="11" pathLength="100" strokeDasharray={`${percentage} ${100 - percentage}`} />
    </svg>
    <strong>{Math.round(percentage)}%</strong>
  </div>;
}

export function RiskGauge({ risk, compact = false }: { risk: RiskResponse; compact?: boolean }) {
  if (risk.value_type === "score") return <div className="instrument-risk">
    <p className="section-heading">Shortfall score</p>
    <p className="mt-4 text-3xl font-semibold">{risk.score.value} <span className="text-sm font-normal text-muted-foreground">on {risk.score.minimum}–{risk.score.maximum}</span></p>
    <p className="mt-3 text-sm">{risk.event_definition}</p>
    <p className="mt-3 text-xs text-muted-foreground">Uncalibrated score; no probability percentage is inferred. {risk.score.higher_means_more_risk ? "Higher" : "Lower"} means more risk.</p>
  </div>;
  const percentage = risk.probability * 100;
  const band = BANDS.find((entry) => percentage < entry.limit)!;
  const calibration = risk.calibration_status.replaceAll("_", " ");
  const limitations = <ul className="mt-2 list-disc space-y-1 pl-4">{risk.limitations.map((item) => <li key={item}>{item}</li>)}</ul>;

  if (compact) return <section aria-label="Shortfall risk" className="instrument-risk print-section">
    <h2 className="section-heading">Shortfall risk</h2>
    <div className="mt-3 flex items-center gap-3">
      <Donut percentage={percentage} stroke={band.stroke} level={band.level} calibration={calibration} />
      <div><span className={`status-label ${band.tone}`}>{band.level}</span><p className="mt-1 text-[10px] leading-4 text-metadata">{risk.provenance.data_origin === "fixture" ? "Illustrative probability" : "Probability estimate"}<br />{calibration}</p></div>
    </div>
    <p className="risk-definition mt-2 text-[11px] leading-4">{risk.event_definition}</p>
    <details className="mt-2 text-[11px] leading-5 text-metadata"><summary className="cursor-pointer text-info">Definition &amp; limitations</summary><p className="mt-2">Demo display bands: Low &lt;30%; Review 30–&lt;60%; Critical ≥60%. Illustrative review bands, not validated operational thresholds. This event is relative to an issued forecast, not a buyer demand target.</p>{limitations}</details>
  </section>;

  return <section aria-label="Shortfall risk" className="instrument-risk print-section">
    <div className="flex items-center justify-between gap-2"><h2 className="section-heading">Shortfall risk</h2><CircleHelp size={16} className="text-metadata" aria-hidden="true" /></div>
    <div className="mt-4 flex items-center gap-5">
      <Donut percentage={percentage} stroke={band.stroke} level={band.level} calibration={calibration} />
      <div><span className={`status-label ${band.tone}`}><AlertTriangle size={14} aria-hidden="true" />{band.level}</span><p className="mt-2 text-xs leading-5 text-metadata">Against the issued forecast.<br />Not a buyer-demand target.</p></div>
    </div>
    <p className="mt-2 text-xs text-metadata">{risk.provenance.data_origin === "fixture" ? "Illustrative probability · demo data" : risk.calibration_status === "validated" ? "Calibrated probability" : "Probability estimate · not calibrated"}</p>
    <p className="risk-definition mt-3 text-sm leading-6">{risk.event_definition}</p>
    <details className="mt-3 text-xs leading-5 text-muted-foreground">
      <summary className="cursor-pointer font-medium text-info">Definition &amp; limitations</summary>
      <p className="mt-2">Demo display bands: Low &lt;30%; Review 30–&lt;60%; Critical ≥60%. These are illustrative review bands, not validated operational thresholds.</p>
      {limitations}
      <p className="mt-2">Calibration: {calibration}. This event is relative to an issued forecast, not a buyer demand target.</p>
    </details>
  </section>;
}
