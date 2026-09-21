import type { Metadata } from "next";
import { InsetBoundary } from "@/components/shell/inset-boundary";
import { FleetSummary } from "@/components/mines/fleet-summary";
import { MineCard } from "@/components/mines/mine-card";
import { loadMineRoster } from "@/lib/api/load";
import s from "@/components/mines/mines.module.css";

export const metadata: Metadata = { title: "Mine Fleet | AVNESH" };

/** Ten model invocations per render, so this page is never prerendered. */
export const dynamic = "force-dynamic";

export default async function MinesPage() {
  const roster = await loadMineRoster();
  const data = roster.data;
  return (
    <div className="workspace-page">
      <header className="mb-7 flex flex-wrap items-start justify-between gap-4 border-b pb-6">
        <div>
          <p className="app-kicker">11 / MINE FLEET</p>
          <h1 className="app-title">Mine Fleet</h1>
          <p className="app-description">
            Every operating MOIL mine, the source its coordinate came from, and what the prospectivity model reads at
            that exact point.
          </p>
        </div>
        <span className="module-status">
          {data
            ? `${data.counts.total} mines · ${data.counts.underground} underground · ${data.counts.opencast} opencast · ` +
              `${data.counts.maharashtra} MH · ${data.counts.madhya_pradesh} MP`
            : "Roster unavailable"}
        </span>
      </header>

      {data ? (
        <>
          <InsetBoundary label="Fleet summary">
            <FleetSummary mines={data.mines} />
          </InsetBoundary>
          <section aria-labelledby="roster-heading">
            <div className={s.sectionHead}>
              <h2 id="roster-heading">Mine roster</h2>
              <span>
                {roster.origin === "fixture"
                  ? "Reference coordinates · scores need the live model"
                  : data.mines.some((mine) => mine.score)
                    ? `${data.provenance.model_version} · scored at the cited coordinates · unmasked`
                    : "Scores unavailable · each card says why"}
              </span>
            </div>
            <InsetBoundary label="Mine roster">
              <div className={s.roster}>
                {data.mines.map((mine) => <MineCard key={mine.name} mine={mine} />)}
              </div>
            </InsetBoundary>
          </section>
        </>
      ) : (
        <p role="alert" className="note">Mine roster unavailable — {roster.error}</p>
      )}

      <p className={s.pageNote}>
        Coordinates are cited, not surveyed: each card says where its point came from and how far it can be trusted.
        Scores are screening indices from satellite imagery and terrain at that point — not reserves, grades or
        recoverable tonnes.
      </p>
    </div>
  );
}
