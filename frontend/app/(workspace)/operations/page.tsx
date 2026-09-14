import Link from "next/link";
import { ArrowUpRight, Diamond, FlaskConical, MapPin, Scan, ArrowRight } from "lucide-react";
import { DEMO_SITES, isGhostReserveCandidate } from "@/fixtures/predictions";
import { actionFixture } from "@/fixtures/operations";
import { loadDashboard, loadForecastBundle, loadRegister } from "@/lib/api/load";
import { ForecastRiskPanel } from "@/components/operations/forecast-risk-panel";
import { ActionEvidence } from "@/components/operations/action-evidence";
import { PrintBriefing } from "@/components/operations/print-briefing";
import { Button } from "@/components/ui/button";
import { VitalSigns } from "@/components/operations/vital-signs";
import { ReviewRegister } from "@/components/operations/review-register";

export default async function HomePage() {
  const [dashboard, bundle, register] = await Promise.all([loadDashboard(), loadForecastBundle(3), loadRegister()]);
  const sites = DEMO_SITES.filter((site) => site.scope_status === "in_scope");
  const candidates = sites.filter(isGhostReserveCandidate);
  return <div className="briefing-page command-page">
    <header className="observatory-hero">
      <div className="hero-copy">
        <p className="app-kicker">01 / OPERATIONS</p>
        <h1>Operational briefing</h1>
        <p className="hero-description">A second look at what mining left behind. Evidence for what comes next.</p>
        <div className="hero-actions mt-6">
          <Link href="/explorer" className="inline-flex items-center justify-center gap-2 px-4 h-10 text-xs font-semibold rounded-sm">
            <Scan size={16} /> Explore the Sausar Belt <ArrowRight size={16} />
          </Link>
          <PrintBriefing />
        </div>
        <p className="hero-provenance">Sausar screening · company-wide forecasts · human review</p>
      </div>
    </header>
    {dashboard.data
      ? <VitalSigns signs={dashboard.data.signs} degraded={dashboard.data.degraded} syntheticNote={dashboard.data.syntheticNote} origin={dashboard.origin} />
      : <p role="alert" className="note">Dashboard summary unavailable — {dashboard.error}</p>}
    
    
    {bundle.data
      ? <ForecastRiskPanel forecast={bundle.data.forecast} risk={bundle.data.risk} riskError={bundle.data.riskError} horizonNote={bundle.data.horizonNote} history={bundle.data.history} />
      : <p role="alert" className="note">Forecast and risk unavailable — {bundle.error}</p>}
    
    
    <div className="briefing-columns mt-6 home-evidence-grid">
      <section className="briefing-register print-section min-w-0 overflow-hidden rounded-lg border bg-surface">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b px-5 py-4"><div><h2 className="section-heading">Brownfield screening register</h2><p className="mt-1 text-xs text-metadata">{candidates.length} Ghost Reserve candidates · Sausar Belt · raw scores before masks</p></div><Button asChild variant="outline" size="sm"><Link href="/explorer">Open Explorer <ArrowUpRight size={14} /></Link></Button></div>
        <div className="overflow-x-auto"><table className="evidence-table">
          <caption className="sr-only">Synthetic screening register and documented farmland diagnostic</caption>
          <thead><tr><th scope="col">Location</th><th scope="col" className="numeric">Raw score</th><th scope="col">5km buffer</th><th scope="col">Next evidence</th></tr></thead>
          <tbody>{sites.map((site) => <tr key={site.id}>
            <th scope="row"><span className="flex items-center gap-2 font-medium text-foreground">{site.asset_type === "diagnostic_point" ? <MapPin size={14} className="shrink-0 text-metadata" /> : <Diamond size={14} className="shrink-0 text-oxide" />}{site.name}</span><span className="mt-1 block text-xs text-metadata">{site.synthetic ? "Synthetic inventory" : "Project-state diagnostic"}</span></th>
            <td className="numeric font-medium">{site.raw_score?.toFixed(2) ?? "—"}</td><td>{site.inside_buffer ? "Inside" : "Outside"}</td><td>{site.synthetic ? "Assay pending" : "Mask comparison"}</td>
          </tr>)}</tbody>
        </table></div>
        <div className="flex items-start gap-2 border-t px-5 py-3 text-xs leading-5 text-muted-foreground"><FlaskConical size={14} className="mt-0.5 shrink-0" />Eligibility identifies candidates for investigation. Recoverable tonnes and environmental clearance are not established.</div>
      </section>
      <div className="space-y-5">
        <ActionEvidence action={actionFixture} />
        <section className="px-1"><h2 className="text-sm font-semibold">Evidence boundary</h2><p className="mt-2 text-xs leading-5 text-muted-foreground">Sausar Belt model scope. Sandur and Bonai return “Outside validated scope”, with no score. Waste-material transfer requires assay validation.</p></section>
      </div>
    
    
    </div><div>
      <div className="pt-1">
        
        {register.data
          ? <ReviewRegister rows={register.data.rows} message={register.data.message} />
          : <p role="alert" className="note">Review register unavailable — {register.error}</p>}
        <footer className="mt-6 flex flex-wrap justify-between gap-2 border-t pt-4 text-xs text-metadata relative z-10"><span>SIH26009 · Mineral Intelligence Workbench</span><span>{bundle.origin === "live" ? "Forecasts and risk are live model output; the waste inventory is a synthetic fixture." : "Forecasts, risk and waste inventory are demonstration fixtures."}</span></footer>
      </div>
    </div>
  </div>;
}
