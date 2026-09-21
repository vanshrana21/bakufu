import { Suspense } from "react";
import Link from "next/link";
import { ArrowUpRight, Scan } from "lucide-react";
import { actionFixture } from "@/fixtures/operations";
import { loadDashboard, loadForecastBundle, loadRegister } from "@/lib/api/load";
import { PrintBriefing } from "@/components/operations/print-briefing";
import { ForecastStrip } from "@/components/operations/forecast-strip";
import { PageHeader } from "@/components/shell/page-header";
import { InsetBoundary } from "@/components/shell/inset-boundary";
import { Button } from "@/components/ui/button";
import { BriefingHumans } from "./briefing-humans";
import { TargetRegister, TargetRegisterFallback } from "./target-register";
import { VitalTiles } from "@/components/operations/vital-tiles";

import s from "./briefing.module.css";

const dateLabel = (iso: string) => new Date(iso).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });

export default async function HomePage() {
  const [dashboard, bundle, register] = await Promise.all([loadDashboard(), loadForecastBundle(3), loadRegister()]);
  const sign = (label: string) => dashboard.data?.signs.find(entry => entry.label === label) ?? null;
  const latest = sign("Latest production"), next = sign("Next-month forecast"), risk = sign("Downside risk");
  const history = bundle.data?.history ?? [];
  const last = history.at(-1), previous = history.at(-2);
  const change = last && previous && previous.tonnes !== 0 ? (last.tonnes - previous.tonnes) / previous.tonnes * 100 : null;
  const forecast = bundle.data?.forecast;
  const rows = register.data?.rows ?? [];
  const proposed = rows.filter(row => row.action.review_status === "proposed").length;
  const drafts = [actionFixture].filter(action => action.rule_version === "draft" && !rows.some(row => row.action.action_id === action.action_id)).length;
  const live = bundle.origin === "live";

  return <div className={`workspace-page operations-page ${s.page}`}>
    <PageHeader kicker="01 / COMMAND" title="Command Center" description="Production, screening and decisions. Your operational picture in one place."
      status={forecast ? `Issued ${dateLabel(forecast.issue_date)} · Data through ${forecast.last_observed_month}` : "Forecast metadata unavailable"}
      actions={<><PrintBriefing /><Button asChild><Link href="/explorer"><Scan size={14} />Open explorer<ArrowUpRight size={14} /></Link></Button></>} />

    {dashboard.data?.syntheticNote && <p role="status" className={`note ${s.notice}`}><strong>Synthetic artifacts.</strong> {dashboard.data.syntheticNote}</p>}
    {dashboard.data && dashboard.data.degraded.length > 0 && <p role="status" className={`note ${s.notice}`}>Degraded components: {dashboard.data.degraded.join(", ")}. Their values are withheld rather than substituted.</p>}
    {dashboard.origin === "fixture" && <p className={s.sourceLine}>Demonstration fixtures · no API configured</p>}

    <VitalTiles latest={latest} next={next} risk={risk} proposed={proposed} drafts={drafts} change={change} history={history} firstForecast={forecast?.points[0]} live={live} registerData={register.data} />

    {bundle.data?.forecast
      ? <section className={s.section}><ForecastStrip forecast={bundle.data.forecast} history={bundle.data.history} /></section>
      : <section className={s.section}><p role="alert" className="note">Forecast and risk unavailable — {bundle.error}</p></section>}

    <Suspense fallback={<TargetRegisterFallback />}>
      <TargetRegister />
    </Suspense>

    <section className={s.section} aria-labelledby="human-heading">
      <div className={s.sectionHead}><div><h2 id="human-heading">Decisions &amp; review</h2><p>Trace every proposal to its trigger. A person approves the next step.</p></div><Link href="/actions" className={s.inlineLink}>All corrective actions<ArrowUpRight size={14} /></Link></div>
      {register.data ? <InsetBoundary label="Review register"><BriefingHumans rows={rows} message={register.data.message} demoRules={[actionFixture]} /></InsetBoundary>
        : <p role="alert" className="note">Review register unavailable — {register.error}</p>}
    </section>
    <footer className={s.honesty}><span>{live ? "API-connected: production · forecast · risk · greenfield targets" : "Synthetic: production · forecast · risk"}</span><span>Synthetic: demo rules. No operational changes executed.</span></footer>
  </div>;
}
