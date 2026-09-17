import Link from "next/link";
import { tonnes } from "@/lib/format";
import type { ForecastResponse } from "@/lib/contracts";
import type { HistoricalPoint } from "./production-chart";
import fs from "./forecast-strip.module.css";

/** Compact forecast summary for /operations: one row with next-month value,
 *  bounds, an inline sparkline, and a deep-link to /production. No toggle,
 *  no axes, no disclosure. */
export function ForecastStrip({ forecast, history }: {
  forecast: ForecastResponse;
  history: readonly HistoricalPoint[];
}) {
  const first = forecast.points[0];
  const pe = first ? tonnes(first.point_estimate) : "—";
  const bounds = first && first.lower_bound !== null && first.upper_bound !== null
    ? `${tonnes(first.lower_bound)}–${tonnes(first.upper_bound)} t`
    : null;

  /* Sparkline data: last 12 actuals + first 3 forecast points. */
  const actuals = history.slice(-12);
  const forecastPts = forecast.points.slice(0, 3);
  const allVals = [...actuals.map(h => h.tonnes), ...forecastPts.map(p => p.point_estimate)];
  const min = Math.min(...allVals);
  const max = Math.max(...allVals);
  const range = max - min || 1;
  const toY = (v: number) => 30 - ((v - min) / range) * 26 - 2;
  const actualPts = actuals.map((h, i) => `${(i / (actuals.length + forecastPts.length - 1)) * 120},${toY(h.tonnes)}`);
  const fPts = forecastPts.map((p, i) => `${((actuals.length + i) / (actuals.length + forecastPts.length - 1)) * 120},${toY(p.point_estimate)}`);
  /* Stitch: last actual connects to first forecast for continuity. */
  const bridgePt = actualPts.length > 0 ? actualPts[actualPts.length - 1] : undefined;

  return (
    <div className={fs.strip}>
      <span className={fs.label}>FORECAST</span>
      <span className={fs.value}>Next month <strong>{pe}</strong> t</span>
      {bounds && <span className={fs.bounds}>{bounds}</span>}
      <svg className={fs.spark} viewBox="0 0 120 32" preserveAspectRatio="none" aria-hidden="true">
        {actualPts.length > 0 && (
          <polyline points={actualPts.join(" ")} fill="none" stroke="var(--observed)" strokeWidth="1.5" />
        )}
        {fPts.length > 0 && (
          <polyline
            points={[bridgePt, ...fPts].filter(Boolean).join(" ")}
            fill="none" stroke="var(--signal)" strokeWidth="1.5" strokeDasharray="4 3" />
        )}
      </svg>
      <Link href="/production" className={fs.link}>Read the full evidence →</Link>
    </div>
  );
}
