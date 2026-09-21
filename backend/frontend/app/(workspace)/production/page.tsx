import { loadForecastBundle, loadRegister } from "@/lib/api/load";
import { tonnes } from "@/lib/format";
import { ForecastRiskPanel } from "@/components/operations/forecast-risk-panel";
import { PrintBriefing } from "@/components/operations/print-briefing";
import { ReviewRegister } from "@/components/operations/review-register";
import { KeyConstraints } from "@/components/operations/survey-outlook";
import { CalendarClock, ShieldCheck } from "lucide-react";

export default async function ProductionPage() {
  const [bundle, register] = await Promise.all([loadForecastBundle(3), loadRegister()]);
  const forecast = bundle.data?.forecast ?? null;
  const next = forecast?.points[0] ?? null;
  // Every date below is read off the response. They were hardcoded strings
  // ("September", "1 September 2026 . UTC"), which would have silently lied the
  // moment live data arrived.
  const fmtMonth = (month: string, part: "month" | "year") =>
    new Date(month + "-01T00:00:00Z").toLocaleDateString("en-IN", part === "month" ? { month: "long", timeZone: "UTC" } : { year: "numeric", timeZone: "UTC" });
  const fmtStamp = (iso: string) =>
    new Date(iso).toLocaleDateString("en-IN", { day: "numeric", month: "long", year: "numeric", timeZone: "UTC" }) + " \u00b7 UTC";
  return <div className="briefing-page production-page operations-page">
    <header className="operations-header">
      <div><p className="app-kicker">03 / PRODUCTION</p><h1>Production &amp; Risk</h1><p>An issued forecast. A defined downside event. The evidence to read both.</p></div>
      <div className="operations-header-tools"><span className="operations-edition">Company-wide · demo scenario</span><PrintBriefing /></div>
    </header>
    <div className="production-layout">
      <aside className="instrument-rail forecast-basis">
        <div className="instrument-rail-label"><CalendarClock size={17} aria-hidden="true" /><h2>Forecast basis</h2></div>
        <p className="forecast-basis-period">{next ? <><span>{fmtMonth(next.month, "month")}</span><span>{fmtMonth(next.month, "year")}</span></> : <span>Unavailable</span>}</p>
        <div className="forecast-basis-estimate"><span>Next-month point estimate</span><p>{next ? <>{tonnes(next.point_estimate)} <small>t</small></> : "\u2014"}</p><span>{bundle.origin === "fixture" ? "Synthetic \u00b7 company-wide" : "Live \u00b7 company-wide"}</span></div>
        <dl className="instrument-metadata">
          <div><dt>Forecast issued</dt><dd>{forecast ? fmtStamp(forecast.issue_date) : "\u2014"}</dd></div>
          <div><dt>Data cutoff</dt><dd>{forecast ? fmtStamp(forecast.data_cutoff) : "\u2014"}</dd></div>
          <div><dt>Last observation</dt><dd>{forecast ? fmtMonth(forecast.last_observed_month, "month") + " " + fmtMonth(forecast.last_observed_month, "year") : "\u2014"}</dd></div>
          <div><dt>Geographic aggregation</dt><dd>MOIL company-wide; no per-mine allocation</dd></div>
        </dl>
        <KeyConstraints />
      </aside>
      {bundle.data
        ? <ForecastRiskPanel forecast={bundle.data.forecast} risk={bundle.data.risk} riskError={bundle.data.riskError} horizonNote={bundle.data.horizonNote} history={bundle.data.history} />
        : <p role="alert" className="note">Forecast and risk unavailable — {bundle.error}</p>}
    </div>
    <section className="forecast-reading" aria-label="Forecast evidence">
      <div className="forecast-reading-label"><ShieldCheck size={20} aria-hidden="true" /><h2>Reading the<br />evidence</h2></div>
      <div className="forecast-reading-grid">
        <div><h3>An interval, not a promise</h3><p>The shaded area shows the supplied 80% prediction interval. <strong>Synthetic bounds · coverage untested</strong>.</p></div>
        <div><h3>A precise shortfall definition</h3><p>September production below 90% of the forecast issued on 1 September. This is distinct from unmet buyer demand.</p></div>
        <div><h3>Events outside the model</h3><p>Sudden strikes, equipment failures and permit disputes are not represented. The model does not predict every operational shock.</p></div>
      </div>
    </section>
    {register.data
      ? <ReviewRegister rows={register.data.rows} message={register.data.message} />
      : <p role="alert" className="note">Review register unavailable — {register.error}</p>}
    <footer className="operations-footer">Illustrative forecasting and risk responses. No live production filings or calibrated performance are claimed.</footer>
  </div>;
}
