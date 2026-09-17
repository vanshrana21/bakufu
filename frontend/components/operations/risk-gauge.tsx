import { AlertTriangle, CircleHelp } from "lucide-react";
import type { RiskResponse } from "@/lib/contracts";

const BANDS = [
  { limit: 30, level: "Low", tone: "text-success", stroke: "var(--success)" },
  { limit: 60, level: "Review", tone: "text-warning", stroke: "var(--warning)" },
  { limit: Infinity, level: "Critical", tone: "text-critical", stroke: "var(--critical)" },
] as const;

export function RiskGauge({ risk, compact = false }: { risk: RiskResponse; compact?: boolean }) {
  if (risk.value_type === "score") {
    return (
      <div className="instrument-risk print-section" style={{ alignSelf: "start" }}>
        <p className="section-heading">Shortfall score</p>
        <p className="mt-4 text-3xl font-semibold">{risk.score.value} <span className="text-sm font-normal text-muted-foreground">on {risk.score.minimum}–{risk.score.maximum}</span></p>
        <p className="mt-3 text-sm">{risk.event_definition}</p>
        <p className="mt-3 text-xs text-muted-foreground">Uncalibrated score; no probability percentage is inferred. {risk.score.higher_means_more_risk ? "Higher" : "Lower"} means more risk.</p>
      </div>
    );
  }

  const percentage = risk.probability * 100;
  const isElevated = percentage >= 30;
  const calibration = risk.calibration_status.replaceAll("_", " ").toUpperCase();
  const limitations = <ul className="mt-2 list-disc space-y-1 pl-4">{risk.limitations.map((item) => <li key={item}>{item}</li>)}</ul>;

  const threshold = (risk as any).threshold ?? 30;
  const delta = (risk as any).delta;
  const previousIssue = (risk as any).previous_issue;

  return (
    <section aria-label="Shortfall risk" className="instrument-risk print-section risk-card" style={{ alignSelf: "start" }}>
      <div className="risk-card-header">
        <span className="risk-label">DOWNSIDE RISK</span>
        <span className={`risk-chip ${isElevated ? 'elevated' : 'low'}`}>
          {isElevated ? <AlertTriangle size={12} strokeWidth={3} /> : <span className="risk-chip-dot" />}
          {isElevated ? 'ELEVATED' : 'LOW'}
        </span>
      </div>

      <div className="risk-number-row">
        <div className="risk-value-wrap">
          <span className="risk-value">{Math.round(percentage)}</span><sup className="risk-sup">%</sup>
        </div>
        {delta !== undefined && (
          <span className={`risk-delta ${delta > 0 ? 'up' : 'down'}`}>
            {delta > 0 ? '↑' : '↓'} {Math.abs(delta)}% vs prev issue
          </span>
        )}
      </div>

      <div className="risk-ruler-wrap" aria-hidden="true">
        <svg className="risk-ruler" viewBox="0 0 100 40" preserveAspectRatio="none">
          {/* Zones */}
          <rect className="ruler-zone moss-zone" x="0" y="20" width={threshold} height="6" />
          <rect className="ruler-zone brick-zone" x={threshold} y="20" width={100 - threshold} height="6" />
          
          {/* Baseline */}
          <line className="ruler-baseline" x1="0" y1="26" x2="100" y2="26" />
          
          {/* Ticks */}
          {[0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100].map(t => (
            <line key={t} x1={t} y1="26" x2={t} y2={t % 50 === 0 ? "29" : "28"} stroke="var(--border)" strokeWidth="0.5" />
          ))}
          
          {/* Numerals */}
          <text x="0" y="36" className="ruler-num" textAnchor="start">0</text>
          <text x="50" y="36" className="ruler-num" textAnchor="middle">50</text>
          <text x="100" y="36" className="ruler-num" textAnchor="end">100</text>
          
          {/* Threshold Tick */}
          {threshold !== undefined && (
            <g className="ruler-threshold-grp">
              <line x1={threshold} y1="20" x2={threshold} y2="29" stroke="var(--action)" strokeWidth="1.5" />
              <text x={threshold} y="15" className="ruler-thresh-lbl" textAnchor="middle">review line</text>
            </g>
          )}

          {/* Headroom bracket */}
          {threshold !== undefined && percentage < threshold && (
            <g className="ruler-bracket">
              <path d={`M ${percentage + 1} 15 L ${percentage + 1} 12 L ${threshold - 1} 12 L ${threshold - 1} 15`} fill="none" stroke="var(--action)" strokeWidth="0.5" />
              <text x={(percentage + threshold) / 2} y="10" className="ruler-bracket-lbl" textAnchor="middle">{Math.round(threshold - percentage)} pts to review line</text>
            </g>
          )}

          {/* Ghost needle */}
          {previousIssue !== undefined && (
             <g className="ruler-ghost">
               <polygon points={`${previousIssue - 1.5},17 ${previousIssue + 1.5},17 ${previousIssue},26`} fill="none" stroke="var(--signal)" strokeWidth="0.5" strokeDasharray="1 1" />
               <text x={previousIssue} y="10" className="ruler-ghost-lbl" textAnchor="middle">June issue: {previousIssue}%</text>
             </g>
          )}

          {/* Needle */}
          <polygon className="ruler-needle" points={`${percentage - 2},17 ${percentage + 2},17 ${percentage},26`} fill="var(--signal)" />
        </svg>
      </div>

      <p className="risk-def-sentence">The chance actual production lands below 90% of the issued forecast for that month.</p>
      
      <p className="risk-calibration-foot">{risk.provenance.data_origin === "fixture" ? "ILLUSTRATIVE PROBABILITY · DEMO DATA" : calibration}</p>

      <details className="mt-2 text-[11px] leading-5 text-metadata">
        <summary className="cursor-pointer font-medium text-info">Definition &amp; limitations</summary>
        <p className="mt-2">Demo display bands: Low &lt;30%; Review 30–&lt;60%; Critical ≥60%. These are illustrative review bands, not validated operational thresholds.</p>
        {limitations}
        <p className="mt-2">This event is relative to an issued forecast, not a buyer demand target.</p>
      </details>
    </section>
  );
}
