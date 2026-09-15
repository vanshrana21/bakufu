import type { CSSProperties } from "react";
import Link from "next/link";
import { ArrowDown, ArrowRight, ArrowUpRight, Check, Clock3, Scan, ShieldAlert, ShieldCheck, TrendingDown, TrendingUp, X } from "lucide-react";
import { DEMO_SITES, isGhostReserveCandidate } from "@/fixtures/predictions";
import { actionFixture } from "@/fixtures/operations";
import { loadDashboard, loadForecastBundle, loadRegister } from "@/lib/api/load";
import { PrintBriefing } from "@/components/operations/print-briefing";
import { TerrainAtmosphere } from "@/components/landing/terrain-atmosphere";
import { Button } from "@/components/ui/button";
import { BriefingForecast } from "./briefing-forecast";
import { BriefingHumans } from "./briefing-humans";
import { Dial, Dot, Sparkline } from "./briefing-parts";
import s from "./briefing.module.css";

/** The page's display bands for the shortfall chance, disclosed under the forecast. */
const RISK_BANDS = [
  { below: 30, gloss: "low right now", sentence: "The chance of falling short is low.", tone: "good" },
  { below: 60, gloss: "high enough to review", sentence: "The chance of falling short is worth a review.", tone: "attention" },
  { below: Infinity, gloss: "high right now", sentence: "The chance of falling short is high.", tone: "attention" },
] as const;

const monthYear = (month: string) =>
  new Date(`${month}-01T00:00:00Z`).toLocaleDateString("en-IN", { month: "long", year: "numeric", timeZone: "UTC" });
const monthShort = (month: string) =>
  new Date(`${month}-01T00:00:00Z`).toLocaleDateString("en-IN", { month: "short", timeZone: "UTC" });
const dayMonthYear = (iso: string) =>
  new Date(iso).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });
const percentChange = (from: number, to: number) => ((to - from) / from) * 100;
const onePlace = (value: number) => Math.abs(value).toFixed(1);

export default async function HomePage() {
  const [dashboard, bundle, register] = await Promise.all([loadDashboard(), loadForecastBundle(3), loadRegister()]);
  const sites = DEMO_SITES.filter((site) => site.scope_status === "in_scope");
  const candidates = sites.filter(isGhostReserveCandidate);
  const live = bundle.origin === "live";

  const sign = (label: string) => dashboard.data?.signs.find((entry) => entry.label === label) ?? null;
  const latest = sign("Latest production");
  const next = sign("Next-month forecast");
  const risk = sign("Downside risk");
  const riskPercent = risk && !risk.unavailable ? Number.parseFloat(risk.value) : Number.NaN;
  const riskBand = Number.isFinite(riskPercent) ? RISK_BANDS.find((band) => riskPercent < band.below)! : null;

  // Every comparison below is arithmetic on values the API returned; nothing is estimated here.
  const history = bundle.data?.history ?? [];
  const lastActual = history.at(-1) ?? null;
  const previousActual = history.at(-2) ?? null;
  const forecast = bundle.data?.forecast ?? null;
  const firstForecast = forecast?.points[0] ?? null;
  const dugChange = lastActual && previousActual ? percentChange(previousActual.tonnes, lastActual.tonnes) : null;
  const expectChange = lastActual && firstForecast ? percentChange(lastActual.tonnes, firstForecast.point_estimate) : null;
  const ahead = forecast?.points ?? [];
  const aheadMax = Math.max(1, ...ahead.map((point) => point.point_estimate), lastActual?.tonnes ?? 0);

  // Counted from exactly what "What needs a human" renders.
  const rows = register.data?.rows ?? [];
  const drafts = [actionFixture].filter((action) =>
    action.rule_version === "draft" && !rows.some((row) => row.action.action_id === action.action_id)).length;
  const proposed = rows.filter((row) => row.action.review_status === "proposed").length;

  const dateLine = `Data through ${forecast ? monthYear(forecast.last_observed_month) : "—"} · Briefing issued ${forecast ? dayMonthYear(forecast.issue_date) : "—"}`;

  const verdicts = [
    dugChange === null ? null : {
      tone: dugChange >= 0 ? "good" : "info",
      icon: dugChange >= 0 ? TrendingUp : TrendingDown,
      text: Math.abs(dugChange) < 0.5 ? "We dug about the same as the month before." : `We dug ${onePlace(dugChange)}% ${dugChange > 0 ? "more" : "less"} than the month before.`,
    },
    expectChange === null ? null : {
      tone: "info",
      icon: expectChange >= 0 ? TrendingUp : TrendingDown,
      text: Math.abs(expectChange) < 0.5 ? "Next month we expect about the same." : `Next month we expect ${onePlace(expectChange)}% ${expectChange > 0 ? "more" : "less"}.`,
    },
    riskBand === null ? null : { tone: riskBand.tone, icon: riskBand.tone === "good" ? ShieldCheck : ShieldAlert, text: riskBand.sentence },
    register.data ? {
      tone: proposed === 0 ? "good" : "attention",
      icon: proposed === 0 ? Check : Clock3,
      text: proposed === 0 ? "Nothing is waiting on a person." : `${proposed} ${proposed === 1 ? "decision is" : "decisions are"} waiting on a person.`,
    } : null,
  ].filter((verdict) => verdict !== null);

  return <div className={s.page}>
    <section className={s.hero} data-theme="dark" aria-labelledby="briefing-title">
      <TerrainAtmosphere variant="waste" />
      <div className={s.heroInner}>
        <div className={s.heroTop}>
          <span className={s.livePill}>
            <Dot tone={live ? "good" : "synthetic"} pulse={live} />{live ? "Live" : "Synthetic"}
          </span>
          <span className={s.heroDate}>{dateLine}</span>
        </div>
        <div className={s.heroGrid}>
          <div>
            <p className={s.heroKicker}>01 / Operations</p>
            <h1 id="briefing-title" className={s.heroTitle}>The morning briefing.</h1>
            <p className={s.heroSub}>Four numbers. One list. <span>Zero surprises.</span></p>
            <div className={`hero-actions ${s.heroActions}`}>
              <Link href="/explorer" className="inline-flex items-center justify-center gap-2 px-4 h-10 text-xs font-semibold rounded-sm">
                <Scan size={16} /> Explore the Sausar Belt <ArrowRight size={16} />
              </Link>
              <PrintBriefing />
            </div>
          </div>
          {verdicts.length > 0 && <div className={s.verdict}>
            <p className={s.verdictLabel}>Today in one breath</p>
            <ul aria-label="Today in one breath">
              {verdicts.map(({ tone, icon: Icon, text }) => <li key={text}>
                <Icon size={18} strokeWidth={2} className={s.verdictIcon} data-tone={tone} aria-hidden="true" />
                {text}
              </li>)}
            </ul>
          </div>}
        </div>
      </div>
    </section>

    <div className={s.inner}>
      {dashboard.data?.syntheticNote && <p role="status" className={`note ${s.notice}`}><strong>Synthetic artifacts.</strong> {dashboard.data.syntheticNote}</p>}
      {dashboard.data && dashboard.data.degraded.length > 0 && <p role="status" className={`note ${s.notice}`}>Degraded components: {dashboard.data.degraded.join(", ")}. Their values are withheld rather than substituted.</p>}
      {dashboard.origin === "fixture" && <p className={s.fixtureNote}>Demonstration fixtures · no API configured</p>}

      <section className={s.stand} aria-labelledby="stand-heading">
        <h2 id="stand-heading" className="sr-only">Where we stand</h2>
        {dashboard.data
          ? <div className={s.grid}>
            <article className={`${s.card} ${s.wide}`} aria-label="Last month we dug">
              <p className={s.cardLabel}>Last month we dug</p>
              {latest && !latest.unavailable
                ? <div className={s.cardSplit}>
                  <div>
                    <p className={s.bigNumber}>{latest.value}<small>t</small></p>
                    <p className={s.gloss}>measured, not guessed</p>
                  </div>
                  {history.length > 1 && <Sparkline values={history.slice(-12).map((point) => point.tonnes)} label={`Measured production for the last ${Math.min(12, history.length)} months`} />}
                </div>
                : <p className={s.gloss}>{latest?.note ?? "Unavailable"}</p>}
            </article>

            <article className={`${s.card} ${s.narrow}`} aria-label="Next month we expect">
              <p className={s.cardLabel}>Next month we expect</p>
              {next && !next.unavailable
                ? <>
                  <p className={s.bigNumber}>{next.value}<small>t</small></p>
                  <p className={s.gloss}>our best guess — range shown below</p>
                  {ahead.length > 0 && lastActual && <div className={s.ahead} role="img" aria-label="Measured last month beside the best guess for each of the next months">
                    <span className={s.aheadBar} data-kind="actual" style={{ "--h": lastActual.tonnes / aheadMax } as CSSProperties}><i /><b>{monthShort(lastActual.month)}</b></span>
                    {ahead.map((point, i) => <span key={point.month} className={s.aheadBar} data-kind={i === 0 ? "next" : "later"} style={{ "--h": point.point_estimate / aheadMax } as CSSProperties}><i /><b>{monthShort(point.month)}</b></span>)}
                  </div>}
                </>
                : <p className={s.gloss}>{next?.note ?? "Unavailable"}</p>}
            </article>

            <article className={`${s.card} ${s.wide} ${s.riskCard}`} data-theme="dark" aria-label="Chance we fall short">
              <p className={s.cardLabel}>Chance we fall short</p>
              {risk && !risk.unavailable && riskBand
                ? <div className={s.cardSplit}>
                  <div>
                    <p className={s.bigNumber}><span data-testid="vital-risk">{risk.value}</span></p>
                    <p className={s.gloss}><Dot tone={riskBand.tone} />{riskBand.gloss}</p>
                  </div>
                  <Dial percent={riskPercent} tone={riskBand.tone} />
                </div>
                : <p className={s.gloss}>{risk?.note ?? "Unavailable"}</p>}
            </article>

            <article className={`${s.card} ${s.narrow}`} aria-label="Waiting on a person">
              <p className={s.cardLabel}>Waiting on a person</p>
              {register.data
                ? <p className={s.bigNumber}>
                  {proposed}<small>proposed</small><span className={s.countSep} aria-hidden="true">·</span>{drafts}<small>draft</small>
                </p>
                : <p className={s.bigNumber}>—</p>}
              <p className={s.gloss}>{register.data ? "decisions, not notifications" : "Recommendations unavailable"}</p>
              <a href="#human-heading" className={s.cardLink}>See the list <ArrowDown size={15} aria-hidden="true" /></a>
            </article>
          </div>
          : <p role="alert" className="note">Dashboard summary unavailable — {dashboard.error}</p>}
      </section>

      <section className={s.section} aria-labelledby="forecast-heading">
        <div className={s.sectionHead}>
          <div>
            <h2 id="forecast-heading" className={s.sectionTitle}>The forecast</h2>
            <p className={s.sectionLead}>The solid line is what we dug. The dashes are what we expect next.</p>
          </div>
        </div>
        {bundle.data
          ? <BriefingForecast forecast={bundle.data.forecast} risk={bundle.data.risk} riskError={bundle.data.riskError} horizonNote={bundle.data.horizonNote} history={bundle.data.history} />
          : <p role="alert" className="note">Forecast and risk unavailable — {bundle.error}</p>}
      </section>

      <section className={s.section} aria-labelledby="places-heading">
        <div className={s.sectionHead}>
          <div>
            <h2 id="places-heading" className={s.sectionTitle}>Places to look</h2>
            <p className={s.sectionLead}>Higher score = more likely the waste still holds metal. A high score is not permission to dig.</p>
          </div>
          <Button asChild variant="outline"><Link href="/explorer">Open the map <ArrowUpRight size={15} aria-hidden="true" /></Link></Button>
        </div>
        <div className={s.tableScroll}>
          <table className={s.places}>
            <caption className="sr-only">Synthetic screening register and documented farmland diagnostic. {candidates.length} Ghost Reserve candidates in the Sausar Belt; scores are raw, before masks.</caption>
            <thead><tr><th scope="col">Place</th><th scope="col">First score (0–1)</th><th scope="col">Inside safety buffer?</th><th scope="col">What happens next</th></tr></thead>
            <tbody>{sites.map((site) => <tr key={site.id}>
              <th scope="row">
                <span className={s.placeName}>{site.name}</span>
                <span className={s.placeKind}>{site.synthetic ? "Synthetic inventory" : "Project-state diagnostic"}</span>
              </th>
              <td data-label="First score (0–1)">{site.raw_score === null
                ? "—"
                : <span className={s.score}>
                  <span className={s.scoreValue}>{site.raw_score.toFixed(2)}</span>
                  <span className={s.bar} aria-hidden="true"><span style={{ "--w": site.raw_score } as CSSProperties} /></span>
                </span>}</td>
              <td data-label="Inside safety buffer?">{site.inside_buffer === null
                ? <span className={s.pill}>Unknown</span>
                : site.inside_buffer
                  ? <span className={s.pill} data-tone="good"><Check size={14} strokeWidth={2.75} aria-hidden="true" />Inside</span>
                  : <span className={s.pill} data-tone="attention"><X size={14} strokeWidth={2.75} aria-hidden="true" />Outside</span>}</td>
              <td className={s.nextStep} data-label="What happens next">{site.synthetic ? "Assay pending" : "Mask comparison"}</td>
            </tr>)}</tbody>
          </table>
        </div>
        <div className={s.footnotes}>
          <p>Eligibility identifies candidates for investigation. Recoverable tonnes and environmental clearance are not established.</p>
          <p>Sausar Belt model scope. Sandur and Bonai return “Outside validated scope”, with no score. Waste-material transfer requires assay validation.</p>
        </div>
      </section>

      <section className={s.section} aria-labelledby="human-heading">
        <div className={s.sectionHead}>
          <div>
            <h2 id="human-heading" className={s.sectionTitle}>What needs a human</h2>
            <p className={s.sectionLead}>The system suggests. A person decides.</p>
          </div>
        </div>
        {register.data
          ? <BriefingHumans rows={register.data.rows} message={register.data.message} demoRules={[actionFixture]} />
          : <p role="alert" className="note">Review register unavailable — {register.error}</p>}
      </section>

      <footer className={s.honesty}>
        {live
          ? <><span><Dot tone="good" />LIVE: production · forecast · risk</span><span><Dot tone="synthetic" />SYNTHETIC: waste list · demo rules</span></>
          : <span><Dot tone="synthetic" />SYNTHETIC: production · forecast · risk · waste list · demo rules</span>}
      </footer>
    </div>
  </div>;
}
