import type { CSSProperties } from "react";
import Link from "next/link";
import { ArrowRight, ArrowUpRight, Check, Diamond, Minus, Scan, TrendingDown, TrendingUp } from "lucide-react";
import { DEMO_SITES, isGhostReserveCandidate } from "@/fixtures/predictions";
import { actionFixture } from "@/fixtures/operations";
import { loadDashboard, loadForecastBundle, loadRegister } from "@/lib/api/load";
import { PrintBriefing } from "@/components/operations/print-briefing";
import { ForecastRiskPanel } from "@/components/operations/forecast-risk-panel";
import { PageHeader } from "@/components/shell/page-header";
import { InsetBoundary } from "@/components/shell/inset-boundary";
import { Button } from "@/components/ui/button";
import { BriefingHumans } from "./briefing-humans";
import { VitalTiles } from "@/components/operations/vital-tiles";

import s from "./briefing.module.css";

const dateLabel = (iso: string) => new Date(iso).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });

export default async function HomePage() {
  const [dashboard, bundle, register] = await Promise.all([loadDashboard(), loadForecastBundle(3), loadRegister()]);
  const sites = DEMO_SITES.filter(site => site.scope_status === "in_scope");
  const candidates = sites.filter(isGhostReserveCandidate);
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

    <section className={s.section} aria-label="Production outlook and downside risk">
      {bundle.data ? <InsetBoundary label="Production outlook"><ForecastRiskPanel forecast={bundle.data.forecast} risk={bundle.data.risk} riskError={bundle.data.riskError} horizonNote={bundle.data.horizonNote} history={bundle.data.history} /></InsetBoundary>
        : <p role="alert" className="note">Forecast and risk unavailable — {bundle.error}</p>}
    </section>

    <section className={s.reserveSection} aria-labelledby="places-heading">
      <div className={s.reserveIntro}>
        <span className={s.reserveIcon}><Diamond size={19} aria-hidden="true" /></span>
        <h2 id="places-heading">Ghost Reserve<br />screening register</h2>
        <p>Investigate the waste already above ground.</p>
        <div className={s.candidateCount}><strong>{String(candidates.length).padStart(2,"0")}</strong><span>candidates within the<br />occurrence buffer</span></div>
        <Link href="/explorer" className={s.inlineLink}>Inspect in explorer<ArrowRight size={14} /></Link>
        <p className={s.reserveCaveat}>Synthetic inventory · assay pending.<br />Not a claim of measured ore.</p>
      </div>
      <div className={s.reserveTable}>
        <div className={s.tableScroll} role="region" aria-label="Screening register" tabIndex={0}>
          <table className={s.places}>
            <caption className="sr-only">Sausar Belt screening locations, raw scores before masks and occurrence buffer membership.</caption>
            <thead><tr><th scope="col">Screening location</th><th scope="col">Raw index</th><th scope="col">5km occurrence buffer</th><th scope="col">Next step</th></tr></thead>
            <tbody>{sites.map(site => <tr key={site.id}>
              <th scope="row"><span className={s.placeName}>{site.name}</span><span className={s.placeKind}>{site.synthetic ? "Synthetic inventory" : "Project-state diagnostic"}</span></th>
              <td><span className={s.score}><span>{site.raw_score?.toFixed(2) ?? "—"}</span>{site.raw_score !== null && <span className={s.bar} aria-hidden="true"><i style={{ "--w": site.raw_score } as CSSProperties} /></span>}</span></td>
              <td><span className={s.pill} data-tone={site.inside_buffer ? "good" : "neutral"}>{site.inside_buffer === null ? <Minus size={12} /> : site.inside_buffer ? <Check size={12} /> : <Minus size={12} />}{site.inside_buffer === null ? "Unknown" : site.inside_buffer ? "Inside" : "Outside"}</span></td>
              <td>{site.synthetic ? "Assay pending" : "Mask comparison"}</td>
            </tr>)}</tbody>
          </table>
        </div>
        <p className={s.footnote}>Raw indices before screening; buffer membership does not establish environmental safety. Recoverable tonnes and environmental clearance are not established.</p>
        <p className={s.footnote}>Sausar Belt model scope. Sandur and Bonai return “Outside validated scope”, with no score. Waste-material transfer requires assay validation.</p>
      </div>
    </section>

    <section className={s.section} aria-labelledby="human-heading">
      <div className={s.sectionHead}><div><h2 id="human-heading">Decisions &amp; review</h2><p>Trace every proposal to its trigger. A person approves the next step.</p></div><Link href="/actions" className={s.inlineLink}>All corrective actions<ArrowUpRight size={14} /></Link></div>
      {register.data ? <InsetBoundary label="Review register"><BriefingHumans rows={rows} message={register.data.message} demoRules={[actionFixture]} /></InsetBoundary>
        : <p role="alert" className="note">Review register unavailable — {register.error}</p>}
    </section>
    <footer className={s.honesty}><span>{live ? "API-connected: production · forecast · risk" : "Synthetic: production · forecast · risk"}</span><span>Synthetic: waste inventory · demo rules. No operational changes executed.</span></footer>
  </div>;
}
