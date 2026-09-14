"use client";

import { Area, CartesianGrid, ComposedChart, Line, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { ForecastResponse } from "@/lib/contracts";
import { tonnes } from "@/lib/format";

export interface HistoricalPoint { month: string; tonnes: number }
interface ChartPoint { month: string; actual: number | null; forecast: number | null; band: [number, number] | null }
export { tonnes };
const monthLabel = (value: string) => new Date(value + "-01T00:00:00Z").toLocaleDateString("en-IN", { month: "short", timeZone: "UTC" });

export function ProductionChart({ forecast, history }: { forecast: ForecastResponse; history: readonly HistoricalPoint[] }) {
  const points: ChartPoint[] = [
    ...history.map((p) => ({ month: p.month, actual: p.tonnes, forecast: null, band: null })),
    ...forecast.points.map((p) => ({ month: p.month, actual: null, forecast: p.point_estimate, band: p.lower_bound !== null && p.upper_bound !== null ? [p.lower_bound, p.upper_bound] as [number, number] : null })),
  ];
  const intervalLabel = forecast.interval ? `${Math.round(forecast.interval.level * 100)}% ${forecast.interval.kind} interval` : "Interval unavailable";
  return <div className="production-chart">
    {/* Legend swatches read their color from the same tokens the marks use, so a
        palette change can never leave the key describing a different series. */}
    <div className="mb-4 flex flex-wrap items-center gap-x-5 gap-y-2 text-xs text-muted-foreground" aria-label="Chart legend">
      <span className="flex items-center gap-2"><span className="chart-legend-line" />Actual series</span>
      <span className="flex items-center gap-2"><span className="chart-legend-line forecast" />Forecast</span>
      <span className="flex items-center gap-2"><span className="h-3 w-5 border border-input bg-[var(--chart-interval)]" />{intervalLabel}</span>
      <span>Forecast begins {forecast.points[0]?.month ?? "—"}</span>
    </div>
    <div className="chart-figure" role="img" aria-label="Monthly production in tonnes. Solid actual series, dashed forecast, bounded interval. Exact values follow in the table.">
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={points} margin={{ left: 8, right: 18, top: 18, bottom: 0 }}>
          <CartesianGrid vertical={false} stroke="var(--border)" strokeDasharray="2 4" />
          <XAxis dataKey="month" tickFormatter={monthLabel} tick={{ fontSize: 12, fill: "var(--metadata)" }} axisLine={false} tickLine={false} minTickGap={24} />
          <YAxis domain={[0, "auto"]} tickFormatter={(v: number) => `${v / 1000}k`} tick={{ fontSize: 12, fill: "var(--metadata)" }} axisLine={false} tickLine={false} width={48} />
          <Tooltip labelFormatter={(label) => `${String(label)} · tonnes`} formatter={(value, name) => [Array.isArray(value) ? value.map((n) => tonnes(Number(n))).join("–") : typeof value === "number" ? tonnes(value) : "Unavailable", name]} contentStyle={{ borderRadius: 3, border: "1px solid var(--input)", color: "var(--foreground)", background: "var(--surface)", fontSize: 13 }} />
          <Area dataKey="band" name={intervalLabel} type="linear" stroke="var(--input)" strokeWidth={1} fill="var(--chart-interval)" fillOpacity={1} isAnimationActive={false} connectNulls={false} />
          <Line dataKey="actual" name="Actual series" type="linear" stroke="var(--chart-actual)" strokeWidth={2.5} dot={{ r: 3 }} isAnimationActive={false} connectNulls={false} />
          <Line dataKey="forecast" name="Forecast" type="linear" stroke="var(--chart-forecast)" strokeWidth={2.5} strokeDasharray="6 4" dot={{ r: 3, fill: "var(--surface)" }} isAnimationActive={false} connectNulls={false} />
          <ReferenceLine x={forecast.points[0]?.month} stroke="var(--metadata)" strokeDasharray="2 4" />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
    <details className="production-values mt-3 text-xs">
      <summary className="cursor-pointer font-medium text-info">View production values and bounds</summary>
      <div className="overflow-x-auto">
        <table className="evidence-table mt-2">
          <caption className="sr-only">Monthly production in tonnes; historical and forecast series</caption>
          <thead><tr><th scope="col">Month</th><th scope="col">Series</th><th scope="col" className="numeric">Value (t)</th><th scope="col" className="numeric">Lower (t)</th><th scope="col" className="numeric">Upper (t)</th></tr></thead>
          {/* A missing value stays an em dash. Zero is a real tonnage, never a placeholder. */}
          <tbody>{points.map((p) => { const value = p.actual ?? p.forecast; return <tr key={p.month}><th scope="row">{p.month}</th><td>{p.actual !== null ? "Actual series" : "Forecast"}</td><td className="numeric">{value === null ? "—" : tonnes(value)}</td><td className="numeric">{p.band ? tonnes(p.band[0]) : "—"}</td><td className="numeric">{p.band ? tonnes(p.band[1]) : "—"}</td></tr>; })}</tbody>
        </table>
      </div>
    </details>
  </div>;
}
