/** MOIL Fleet Intelligence: the ten mines, their cited coordinates and what
 * the model reads at each one.
 *
 * Page shell matched from app/(workspace)/production/page.tsx: an async Server
 * Component that awaits a loader from lib/api/load.ts, renders a `note` with
 * role="alert" when the loader failed, and uses the shared PageHeader rhythm
 * (components/shell/page-header.tsx). Container class `workspace-page` comes
 * from components/shell/workspace.css, as the other module pages use.
 */

import type { Metadata } from "next";
import { MapPin } from "lucide-react";
import { loadMineRoster } from "@/lib/api/load";
import { Badge } from "@/components/ui/badge";
import { PageHeader } from "@/components/shell/page-header";
import { FleetSummary } from "@/components/mines/fleet-summary";
import { MineRosterGrid } from "@/components/mines/mine-roster";

export const metadata: Metadata = {
  title: "MOIL Fleet Intelligence | Mineral Intelligence",
};

/** Ten model invocations per render, so this is never statically prerendered. */
export const dynamic = "force-dynamic";

export default async function MinesPage() {
  const roster = await loadMineRoster();

  return (
    <div className="workspace-page">
      <PageHeader
        title="MOIL Fleet Intelligence"
        description="Every operating mine, the source its coordinate came from, and what the prospectivity model reads at that exact point."
        status={
          roster.data ? (
            <Badge variant="outline">
              <MapPin size={13} aria-hidden="true" />
              {roster.data.counts.total} mines · {roster.data.counts.underground} underground ·{" "}
              {roster.data.counts.opencast} opencast
            </Badge>
          ) : (
            <Badge variant="warning">Roster unavailable</Badge>
          )
        }
      />

      {roster.data ? (
        <div className="space-y-6">
          <FleetSummary mines={roster.data.mines} />
          <section aria-labelledby="roster-heading">
            <div className="mb-3 flex items-baseline justify-between gap-3">
              <h2 id="roster-heading" className="text-base font-semibold">
                Mine roster
              </h2>
              <span className="font-mono text-xs text-muted-foreground">
                {roster.data.provenance.model_version} · scored at the cited coordinates
              </span>
            </div>
            <MineRosterGrid mines={roster.data.mines} />
          </section>
          <p className="border-t pt-4 text-xs leading-5 text-muted-foreground">
            Scores are screening indices on a 0–0.99 scale, not recovery probabilities or
            ore quantities, and they describe a single pixel: values move sharply within a
            kilometre. Coordinate confidence is the researcher&apos;s, not the
            model&apos;s — a confident score at an uncertain coordinate describes some
            ground, not necessarily that mine.
          </p>
        </div>
      ) : (
        <p role="alert" className="note">
          Mine roster unavailable — {roster.error}
        </p>
      )}
    </div>
  );
}
