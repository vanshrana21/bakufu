"use client";

import { useEffect, useRef, useState } from "react";
import { Area, CartesianGrid, ComposedChart, Line, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { ForecastResponse, RiskResponse } from "@/lib/contracts";
import type { HistoricalPoint } from "@/components/operations/production-chart";
import { tonnes } from "@/lib/format";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import s from "./briefing.module.css";

interface ChartPoint { month: string; actual: number | null; forecast: number | null; band: [number, number] | null }

const monthLabel = (value: string) =>
  new Date(`${value}-01T00:00:00Z`).toLocaleDateString("en-IN", { month: "short", timeZone: "UTC" });

/** Block 2: a dark instrument. The chart draws itself once on arrival; the side
 * rail holds the only printed range on the page and what "falling short" means. */
export function BriefingForecast({ forecast, risk, riskError = null, horizonNote = null, history }: {
  forecast: ForecastResponse;
  risk: RiskResponse | null;
  riskError?: string | null;
  horizonNote?: string | null;
  history: readonly HistoricalPoint[];
}) {
  const [horizon, setHorizon] = useState("3");
  // Rendered after mount so the draw-in can honour the viewer's motion setting.
  const [motion, setMotion] = useState<boolean | null>(null);
  // Mounted when the panel scrolls into view, so the draw-in is seen rather than
  // spent off-screen. Printing mounts it immediately.
  const figure = useRef<HTMLDivElement>(null);
  const [inView, setInView] = useState(false);
  // A year of history leaves the forecast months readable; a phone gets eight months.
  const [compact, setCompact] = useState(false);
  useEffect(() => {
    setMotion(!window.matchMedia("(prefers-reduced-motion: reduce)").matches);
    const narrow = window.matchMedia("(max-width: 600px)");
    const sync = () => setCompact(narrow.matches);
    sync();
    narrow.addEventListener("change", sync);
    return () => narrow.removeEventListener("change", sync);
  }, []);
  useEffect(() => {
    const node = figure.current;
    const show = () => setInView(true);
    window.addEventListener("beforeprint", show);
    if (!node || typeof IntersectionObserver === "undefined") { show(); return () => window.removeEventListener("beforeprint", show); }
    const observer = new IntersectionObserver((entries) => {
      if (entries.some((entry) => entry.isIntersecting)) { show(); observer.disconnect(); }
    }, { threshold: 0.25 });
    observer.observe(node);
    return () => { observer.disconnect(); window.removeEventListener("beforeprint", show); };
  }, []);

  const points = horizon === "1" ? forecast.points.slice(0, 1) : forecast.points;
  const data: ChartPoint[] = [
    ...history.slice(compact ? -8 : -12).map((p) => ({ month: p.month, actual: p.tonnes, forecast: null, band: null })),
    ...points.map((p) => ({
      month: p.month, actual: null, forecast: p.point_estimate,
      band: p.lower_bound !== null && p.upper_bound !== null ? [p.lower_bound, p.upper_bound] as [number, number] : null,
    })),
  ];
  const first = forecast.points[0];
  const level = forecast.interval ? Math.round(forecast.interval.level * 100) : null;
  const hasRange = first !== undefined && first.lower_bound !== null && first.upper_bound !== null;
  const animate = motion === true;

  return <div className={s.forecastPanel} data-theme="dark">
    <div className={`print-section ${s.chartColumn}`}>
      <div className={s.chartBar}>
        <div className={s.legend} aria-label="Chart legend">
          <span><i className={s.swatchActual} aria-hidden="true" />What really happened</span>
          <span><i className={s.swatchGuess} aria-hidden="true" />Our best guess</span>
          <span><i className={s.swatchBand} aria-hidden="true" />Where the truth usually lands</span>
        </div>
        <Tabs value={horizon} onValueChange={setHorizon} className="no-print">
          <TabsList aria-label="Forecast horizon"><TabsTrigger value="1">1 month</TabsTrigger><TabsTrigger value="3">3 months</TabsTrigger></TabsList>
        </Tabs>
      </div>
      {horizonNote && <p role="status" className={`note ${s.notice}`}>{horizonNote}</p>}
      <div ref={figure} className={s.chartFigure} role="img" aria-label="Monthly production in tonnes. Solid line for measured months, dashed line for the best guess, shaded band for the range. Exact values follow in the table.">
        {motion !== null && inView && <ResponsiveContainer width="100%" height="100%">
          <ComposedChart key={horizon} data={data} margin={{ left: 4, right: 12, top: 16, bottom: 0 }}>
            <defs>
              <linearGradient id="briefing-actual-fill" x1="0" x2="0" y1="0" y2="1">
                <stop offset="0" stopColor="var(--glow)" stopOpacity={0.28} />
                <stop offset="1" stopColor="var(--glow)" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid vertical={false} stroke="var(--border)" strokeDasharray="2 5" />
            <XAxis dataKey="month" tickFormatter={monthLabel} tick={{ fontSize: 13, fill: "var(--muted-foreground)" }} axisLine={false} tickLine={false} minTickGap={28} />
            <YAxis domain={[0, "auto"]} tickFormatter={(v: number) => `${v / 1000}k`} tick={{ fontSize: 13, fill: "var(--muted-foreground)" }} axisLine={false} tickLine={false} width={52} />
            <Tooltip
              labelFormatter={(label) => `${monthLabel(String(label))} · tonnes`}
              formatter={(value, name) => [Array.isArray(value) ? value.map((n) => tonnes(Number(n))).join(" – ") : typeof value === "number" ? tonnes(value) : "Unavailable", name]}
              contentStyle={{ borderRadius: 4, border: "1px solid var(--border)", color: "var(--foreground)", background: "var(--surface)", fontSize: 13 }}
              cursor={{ stroke: "var(--border-strong)", strokeDasharray: "3 4" }}
            />
            <Area dataKey="actual" name="What really happened" type="linear" stroke="none" fill="url(#briefing-actual-fill)" tooltipType="none" isAnimationActive={animate} animationDuration={1400} connectNulls={false} />
            <Area dataKey="band" name="Where the truth usually lands" type="linear" stroke="var(--glow)" strokeOpacity={0.35} strokeWidth={1} fill="var(--chart-interval)" fillOpacity={1} isAnimationActive={animate} animationBegin={1100} animationDuration={700} connectNulls={false} />
            <Line dataKey="actual" name="What really happened" type="linear" stroke="var(--chart-actual)" strokeWidth={2.5} dot={false} activeDot={{ r: 5 }} isAnimationActive={animate} animationDuration={1400} connectNulls={false} />
            <Line dataKey="forecast" name="Our best guess" type="linear" stroke="var(--chart-forecast)" strokeWidth={3} strokeDasharray="7 5" dot={{ r: 4, fill: "var(--background)", strokeWidth: 2 }} isAnimationActive={animate} animationBegin={1100} animationDuration={700} connectNulls={false} />
            <ReferenceLine x={forecast.points[0]?.month} stroke="var(--border-strong)" strokeDasharray="2 4" label={{ value: "next", position: "insideTopRight", fill: "var(--muted-foreground)", fontSize: 12 }} />
          </ComposedChart>
        </ResponsiveContainer>}
      </div>
      <details className={s.values}>
        <summary>See the numbers</summary>
        <div className={s.tableScroll}>
          <table>
            <caption className="sr-only">Monthly production in tonnes; measured months and the best guess with its range</caption>
            <thead><tr><th scope="col">Month</th><th scope="col">Series</th><th scope="col">Value (t)</th><th scope="col">Lower (t)</th><th scope="col">Upper (t)</th></tr></thead>
            <tbody>{data.map((p) => {
              const value = p.actual ?? p.forecast;
              return <tr key={p.month}><th scope="row">{p.month}</th><td>{p.actual !== null ? "What really happened" : "Our best guess"}</td><td>{value === null ? "—" : tonnes(value)}</td><td>{p.band ? tonnes(p.band[0]) : "—"}</td><td>{p.band ? tonnes(p.band[1]) : "—"}</td></tr>;
            })}</tbody>
          </table>
        </div>
      </details>
      <p className={s.modelNote}>
        {forecast.provenance.data_origin === "fixture"
          ? "All plotted values, including the actual-series example, are synthetic. Interval coverage has not been validated."
          : forecast.provenance.source}
      </p>
    </div>

    <aside className={s.rail} aria-label="Reading the forecast">
      <div className={s.railBlock}>
        <p className={s.railLabel}>Next month{level !== null ? `, ${level}% range` : ""}</p>
        <p className={s.range}>{hasRange ? <>{tonnes(first.lower_bound!)}<span className={s.rangeDash}>–</span>{tonnes(first.upper_bound!)} <small>t</small></> : "Range unavailable"}</p>
        <p className={s.railText}>The glowing band on the chart.</p>
      </div>
      <div className={s.railBlock}>
        <p className={s.railLabel}>Falling short means</p>
        {risk === null
          ? <p role="status" className={s.railText}>Shortfall risk unavailable{riskError ? ` — ${riskError}` : "."} No probability has been substituted.</p>
          : risk.reference_forecast_id !== forecast.forecast_id
            ? <p role="alert" className={s.railText}>Risk references a different forecast. A combined interpretation is unavailable.</p>
            : <>
              <p className={s.railText}>{risk.event_definition}</p>
              <p className={s.calibration}>
                {risk.provenance.data_origin === "fixture" ? "Illustrative probability · demo data" : risk.calibration_status === "validated" ? "Calibrated probability" : "Probability estimate · not calibrated"}
              </p>
              <details className={s.details}>
                <summary>Definition &amp; limitations</summary>
                <p>Demo display bands: Low &lt;30%; Review 30–&lt;60%; Critical ≥60%. These are illustrative review bands, not validated operational thresholds.</p>
                <ul>{risk.limitations.map((item) => <li key={item}>{item}</li>)}</ul>
                <p>Calibration: {risk.calibration_status.replaceAll("_", " ")}. This event is relative to an issued forecast, not a buyer demand target.</p>
              </details>
            </>}
      </div>
    </aside>
  </div>;
}
