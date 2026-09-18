"use client";

/** Roster grid, with the score explanation expanding inside the card.
 *
 * Grid matched from components/assets/MineOverviewGrid.tsx
 * (`grid gap-4 sm:grid-cols-2 xl:grid-cols-3`), as are the card internals:
 * CardHeader with a title, a muted sub-line and a Badge on the right, then a
 * CardContent of dt/dd pairs in mono. Score typography matched from the
 * ScoreTile in components/explorer/site-inspector.tsx
 * (`text-[34px] font-semibold leading-none tracking-tight`). The disclosure
 * control is the existing Button `link` variant.
 *
 * The detail expands in place rather than opening a modal: there is no Dialog
 * primitive in this codebase, and its established "why this score" surface is
 * the Explorer's inspector panel. An inline disclosure reuses the card's own
 * typography, needs no focus trap or portal, and works unchanged at phone
 * width where a modal would have to become a sheet.
 */

import { useState } from "react";
import { ChevronDown, ChevronRight, ExternalLink } from "lucide-react";
import { Badge, type BadgeProps } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { Mine } from "@/lib/contracts";
import { GROUP_VARIANT, groupOf } from "./fleet-summary";

const CONFIDENCE: Record<
  Mine["coordinate_confidence"],
  { label: string; variant: BadgeProps["variant"] }
> = {
  high: { label: "High confidence", variant: "success" },
  medium_high: { label: "Medium-high", variant: "info" },
  low_medium: { label: "Low-medium", variant: "warning" },
  low: { label: "Low confidence", variant: "warning" },
  none: { label: "Unverified", variant: "destructive" },
};

const SCORE_CAPTION = {
  recognised: "Recognised by the model",
  mixed: "Mixed signal · verify in the field",
  low: "Low · read the caveat",
} as const;

type Drivers = NonNullable<Mine["score"]>["drivers"];

function DriverList({ title, drivers }: { title: string; drivers: Drivers }) {
  if (drivers.length === 0) {
    return (
      <div>
        <p className="text-xs font-medium">{title}</p>
        <p className="mt-1 text-xs text-muted-foreground">
          None among the five contributions the model returns.
        </p>
      </div>
    );
  }
  return (
    <div>
      <p className="text-xs font-medium">{title}</p>
      <dl className="mt-1 space-y-1">
        {drivers.map((driver) => (
          <div key={driver.feature} className="flex items-baseline justify-between gap-3">
            <dt className="text-xs text-muted-foreground">{driver.label}</dt>
            <dd className="font-mono text-xs tabular-nums">
              {driver.contribution > 0 ? "+" : ""}
              {driver.contribution.toFixed(3)}
            </dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

function MineCard({ mine }: { mine: Mine }) {
  const [open, setOpen] = useState(false);
  const group = groupOf(mine);
  const confidence = CONFIDENCE[mine.coordinate_confidence];
  const detailId = `mine-detail-${mine.name.replaceAll(" ", "-").toLowerCase()}`;
  // Positive SHAP argues for prospectivity, negative against. The backend
  // returns its top five by magnitude, so one side can be empty.
  const up = (mine.score?.drivers ?? []).filter((d) => d.contribution > 0)
    .sort((a, b) => b.contribution - a.contribution);
  const down = (mine.score?.drivers ?? []).filter((d) => d.contribution < 0)
    .sort((a, b) => a.contribution - b.contribution);

  return (
    <Card>
      <CardHeader className="flex-row items-start justify-between gap-3">
        <div>
          <CardTitle>{mine.name}</CardTitle>
          <p className="mt-1 text-xs text-muted-foreground">
            {mine.state} · {mine.district}
          </p>
        </div>
        <Badge variant="outline">{mine.mine_type}</Badge>
      </CardHeader>
      <CardContent>
        <div className="flex items-end justify-between gap-4">
          <div>
            <p
              className="text-[34px] font-semibold leading-none tracking-tight tabular-nums"
              data-testid={`mine-score-${mine.name.replaceAll(" ", "-").toLowerCase()}`}
            >
              {mine.score ? mine.score.value.toFixed(2) : "—"}
            </p>
            <p className="mt-2 text-xs text-muted-foreground">
              {mine.score && group ? SCORE_CAPTION[group] : "No score at this coordinate"}
            </p>
          </div>
          {mine.score && group && <Badge variant={GROUP_VARIANT[group]}>{group === "recognised" ? "Recognised" : group === "mixed" ? "Mixed" : "Low"}</Badge>}
        </div>

        {mine.score_error && (
          <p className="mt-3 text-xs leading-5 text-muted-foreground">{mine.score_error}</p>
        )}

        <div className="mt-4 border-t pt-3">
          <Badge variant={confidence.variant}>{confidence.label}</Badge>
          <p className="mt-2 text-xs leading-5 text-muted-foreground">
            {mine.coordinate_source_url ? (
              <a
                className="inline-flex items-center gap-1 underline underline-offset-4"
                href={mine.coordinate_source_url}
                target="_blank"
                rel="noreferrer"
              >
                {mine.coordinate_source}
                <ExternalLink size={12} aria-hidden="true" />
              </a>
            ) : (
              mine.coordinate_source
            )}
          </p>
          <p className="mt-1 font-mono text-xs tabular-nums text-muted-foreground">
            {mine.location.latitude.toFixed(4)}, {mine.location.longitude.toFixed(4)}
          </p>
        </div>

        <Button
          variant="link"
          size="sm"
          className="mt-2 h-auto px-0"
          aria-expanded={open}
          aria-controls={detailId}
          onClick={() => setOpen((current) => !current)}
        >
          {open ? <ChevronDown size={14} aria-hidden="true" /> : <ChevronRight size={14} aria-hidden="true" />}
          Why this score?
        </Button>

        {open && (
          <div id={detailId} className="mt-3 space-y-4 border-t pt-3">
            {mine.score ? (
              <>
                <div className="grid gap-4 sm:grid-cols-2">
                  <DriverList title="Pushing the score up" drivers={up} />
                  <DriverList title="Pushing the score down" drivers={down} />
                </div>
                <p className="text-xs leading-5 text-muted-foreground">
                  Contributions are log-odds from the underlying classifier, before the
                  positive-unlabelled adjustment and the 0.99 cap. Scored by{" "}
                  {mine.score.model_version}.
                </p>
              </>
            ) : (
              <p className="text-xs leading-5 text-muted-foreground">
                No contributions: the model produced no score at this coordinate.
              </p>
            )}
            {mine.coordinate_precision && (
              <p className="text-xs leading-5 text-muted-foreground">
                Coordinate precision: {mine.coordinate_precision}
              </p>
            )}
            {mine.coordinate_note && (
              <p className="text-xs leading-5 text-muted-foreground">{mine.coordinate_note}</p>
            )}
            {mine.caveat && <p className="note">{mine.caveat}</p>}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

export function MineRosterGrid({ mines }: { mines: readonly Mine[] }) {
  if (mines.length === 0) {
    return (
      <p role="alert" className="note">
        The roster returned no mines. Nothing is rendered rather than a placeholder fleet.
      </p>
    );
  }
  return (
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
      {mines.map((mine) => (
        <MineCard key={mine.name} mine={mine} />
      ))}
    </div>
  );
}
