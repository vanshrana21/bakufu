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
      <div className="instrument-risk print-section" style={{ alignSelf: "start", height: "fit-content" }}> 
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
    <section aria-label="Shortfall risk" className="instrument-risk print-section risk-card" style={{ alignSelf: "start", height: "fit-content" }}>
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

      <div className="risk-ruler-wrap" aria-hidden="true" style={{ position: 'relative', marginTop: '30px', marginBottom: '20px' }}>
        
        {/* Headroom Bracket (HTML Overlay) */}
        {threshold !== undefined && percentage < threshold && (
           <div className="ruler-bracket" style={{ position: 'absolute', left: `${percentage}%`, right: `${100 - threshold}%`, bottom: '100%', marginBottom: '8px' }}>
             <div style={{ height: '4px', borderTop: '1px solid var(--action)', borderLeft: '1px solid var(--action)', borderRight: '1px solid var(--action)' }}></div>
             <span className="ruler-bracket-lbl" style={{ position: 'absolute', bottom: '100%', left: '50%', transform: 'translateX(-50%)', marginBottom: '4px', whiteSpace: 'nowrap' }}>
               {Math.round(threshold - percentage)} pts to review line
             </span>
           </div>
        )}

        <svg className="risk-ruler" viewBox="0 0 100 24" preserveAspectRatio="none" style={{ display: 'block', width: '100%', height: '24px', overflow: 'visible' }}>
          {/* Zones */}
          <rect className="ruler-zone moss-zone" x="0" y="8" width={threshold} height="6" />
          <rect className="ruler-zone brick-zone" x={threshold} y="8" width={100 - threshold} height="6" />
          
          {/* Baseline */}
          <line className="ruler-baseline" x1="0" y1="14" x2="100" y2="14" stroke="var(--border)" strokeWidth="1" />
          
          {/* Ticks (hairlines) */}
          {[0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100].map(t => (
            <line key={t} x1={t} y1="14" x2={t} y2={t % 50 === 0 ? "18" : "16"} stroke="var(--border)" strokeWidth="0.5" />
          ))}
          
          {/* Threshold Tick */}
          {threshold !== undefined && (
            <line x1={threshold} y1="8" x2={threshold} y2="18" stroke="var(--action)" strokeWidth="1.5" className="ruler-thresh-tick" />
          )}

          {/* Ghost needle */}
          {previousIssue !== undefined && (
             <g className="ruler-ghost">
               <polygon points={`${previousIssue - 1.5},5 ${previousIssue + 1.5},5 ${previousIssue},14`} fill="none" stroke="var(--signal)" strokeWidth="0.5" strokeDasharray="1 1" />
             </g>
          )}

          {/* Needle */}
          <polygon className="ruler-needle" points={`${percentage - 2},5 ${percentage + 2},5 ${percentage},14`} fill="var(--signal)" />
        </svg>

        {/* Numerals (HTML Overlay) */}
        <span className="ruler-num" style={{ position: 'absolute', left: '0%', top: '100%', marginTop: '6px', transform: 'translateX(0%)' }}>0</span>
        <span className="ruler-num" style={{ position: 'absolute', left: '50%', top: '100%', marginTop: '6px', transform: 'translateX(-50%)' }}>50</span>
        <span className="ruler-num" style={{ position: 'absolute', left: '100%', top: '100%', marginTop: '6px', transform: 'translateX(-100%)' }}>100</span>

        {/* Threshold Tick Label (HTML Overlay) */}
        {threshold !== undefined && (
           <span className="ruler-thresh-lbl" style={{ position: 'absolute', left: `${threshold}%`, top: '100%', transform: 'translateX(-50%)', marginTop: '6px', whiteSpace: 'nowrap' }}>
             review line
           </span>
        )}

        {/* Ghost Label (HTML Overlay) */}
        {previousIssue !== undefined && (
           <span className="ruler-ghost-lbl" style={{ position: 'absolute', left: `${previousIssue}%`, bottom: '100%', transform: 'translateX(-50%)', marginBottom: '8px', whiteSpace: 'nowrap' }}>
             June issue: {previousIssue}%
           </span>
        )}
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
