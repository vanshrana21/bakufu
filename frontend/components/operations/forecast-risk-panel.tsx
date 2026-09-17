"use client";

import { useState } from "react";
import type { ForecastResponse, RiskResponse } from "@/lib/contracts";
import { ProductionChart, tonnes, type HistoricalPoint } from "./production-chart";
import { RiskGauge } from "./risk-gauge";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";

/** Full-system example: typed evidence, query horizon, uncertainty, accessible table,
 * neutral surfaces, semantic states, and a related risk which keeps its own horizon. */
export function ForecastRiskPanel({ forecast, risk, riskError = null, horizonNote = null, history }: {
  forecast: ForecastResponse;
  /** Null when the shortfall component is degraded; the forecast still renders. */
  risk: RiskResponse | null;
  riskError?: string | null;
  /** Explains a chart showing fewer months than the selected horizon. */
  horizonNote?: string | null;
  history: readonly HistoricalPoint[];
}) {
  const [horizon, setHorizon] = useState("3");
  const first = forecast.points[0];
  const displayedForecast = horizon === "1" ? { ...forecast, horizon_months: 1 as const, points: forecast.points.slice(0, 1) } : forecast;
  const issueDate = new Date(forecast.issue_date).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });
  return <div className="briefing-columns forecast-risk-layout relative">
    <section className="forecast-instrument print-section min-w-0 rounded-lg border bg-surface" aria-labelledby="forecast-heading">
      <div className="flex flex-wrap items-start justify-between gap-3 px-5 pt-5">
        <div>
          <p className="section-label mb-2">FORECAST</p>
          <h2 id="forecast-heading" className="section-heading">Production outlook</h2>
          <p className="mt-1 text-xs text-metadata">MOIL company-wide · tonnes · issued {issueDate}</p>
        </div>
        <Tabs value={horizon} onValueChange={setHorizon} className="no-print"><TabsList aria-label="Forecast horizon"><TabsTrigger value="1">1 month</TabsTrigger><TabsTrigger value="3">3 months</TabsTrigger></TabsList></Tabs>
      </div>
      <div className="mx-5 my-3 flex flex-wrap items-center gap-x-5 gap-y-2 border-b pb-3 text-sm">
        <span>Next month <strong className="ml-1 font-semibold" data-kind="model">{first ? tonnes(first.point_estimate) : "Unavailable"} t</strong></span>
        <span className="text-muted-foreground">{first?.lower_bound !== null && first?.upper_bound !== null && first ? `${tonnes(first.lower_bound)}–${tonnes(first.upper_bound)} t` : "Bounds unavailable"}</span>
      </div>
      {horizonNote && <p role="status" className="note mx-5 mb-3">{horizonNote}</p>}
      <div className="px-4 pb-4"><ProductionChart forecast={displayedForecast} history={history} /></div>
      <p className="border-t px-5 py-3 text-xs leading-5 text-metadata">{forecast.provenance.data_origin === "fixture" ? "All plotted values, including the actual-series example, are synthetic. Interval coverage has not been validated." : forecast.provenance.source}</p>
    </section>
    <aside className="risk-instrument rounded-lg border bg-surface p-5">
      <p className="section-label mb-4 block">DOWNSIDE RISK</p>
      {risk === null
        ? <p role="status" className="note">Shortfall risk unavailable{riskError ? ` — ${riskError}` : "."} No probability has been substituted.</p>
        : risk.reference_forecast_id === forecast.forecast_id
          ? <RiskGauge risk={risk} />
          : <p role="alert">Risk references a different forecast. A combined interpretation is unavailable.</p>}
    </aside>
  </div>;
}
