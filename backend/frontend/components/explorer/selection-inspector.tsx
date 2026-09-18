"use client";

/** Evidence for whatever the map has selected: an operating mine, or one of
 * the model's targets.
 *
 * Replaces the fixture site inspector. Both selections are coordinates, so the
 * same /predict/point call explains either, under the mask the Explorer has
 * active. Layout, tabs and score tiles are the shell the fixture inspector
 * used, so the panel reads exactly as before.
 */

import { Crosshair, MapPin, Radar, ShieldAlert, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import type { MineLocation, Target } from "@/lib/contracts";
import { usePointExplanation } from "@/hooks/use-point-explanation";
import { useExplorerStore } from "./explorer-provider";
import { ShapBarChart } from "./shap-bar-chart";

function ScoreTile({
  label,
  value,
  tone = "neutral",
}: {
  label: string;
  value: number | null;
  tone?: "neutral" | "primary";
}) {
  return (
    <div className={tone === "primary" ? "border-b-2 border-primary pb-4" : "border-b pb-4"}>
      <p className="text-xs font-medium text-muted-foreground">{label}</p>
      <p
        className="mt-2 text-[34px] font-semibold leading-none tracking-tight tabular-nums"
        data-testid={label.toLowerCase().includes("raw") ? "raw-score" : "final-score"}
      >
        {value?.toFixed(2) ?? "—"}
      </p>
    </div>
  );
}

export function SelectionInspector({
  mines,
  targets,
}: {
  mines: readonly MineLocation[];
  targets: readonly Target[];
}) {
  const selected = useExplorerStore((s) => s.selected);
  const mask = useExplorerStore((s) => s.activeMask);
  const select = useExplorerStore((s) => s.select);

  const mine = selected?.kind === "mine" ? (mines.find((m) => m.name === selected.id) ?? null) : null;
  const target =
    selected?.kind === "target" ? (targets.find((t) => t.id === selected.id) ?? null) : null;
  const location = mine?.location ?? target?.location ?? null;
  const { data, loading, noImagery, error } = usePointExplanation(location, mask);

  const title = mine?.name ?? (target ? target.id : null);
  const subtitle = mine
    ? `Operating mine · ${mine.district}, ${mine.state}`
    : target
      ? `Model target · ${target.label}`
      : null;

  return (
    <aside className="inspector" aria-label="Selection inspector" aria-busy={loading}>
      <div className="flex h-14 items-center justify-between border-b px-5">
        <span className="text-xs font-semibold text-muted-foreground">Selection inspector</span>
        <Button variant="ghost" size="icon" aria-label="Clear selection" onClick={() => select(null)}>
          <X size={16} />
        </Button>
      </div>
      <div className="p-5" aria-live="polite">
        {!selected && (
          <div className="py-14 text-center">
            <div className="mx-auto mb-5 flex h-14 w-14 items-center justify-center rounded-xl bg-muted">
              <MapPin size={25} className="text-muted-foreground" />
            </div>
            <h2 className="text-lg font-semibold">Inspect a location</h2>
            <p className="mx-auto mt-3 max-w-64 text-sm leading-6 text-muted-foreground">
              Choose a mine or a model target, on the map or in the lists, to see its score and the
              features behind it.
            </p>
          </div>
        )}

        {selected && (
          <>
            <div className="mb-4 flex items-center justify-between gap-3">
              <Badge variant={mine ? "secondary" : "default"}>
                {mine ? <MapPin size={13} aria-hidden="true" /> : <Crosshair size={13} aria-hidden="true" />}
                {mine ? "Operating mine" : "Model target"}
              </Badge>
              <span className="text-xs text-metadata">{mask.replaceAll("_", " ")} mask</span>
            </div>
            <h2 className="text-[24px] font-semibold leading-tight tracking-tight">{title}</h2>
            <p className="mt-2 text-xs text-muted-foreground">{subtitle}</p>
            {location && (
              <p className="mt-2 font-mono text-xs tabular-nums text-muted-foreground">
                {location.latitude.toFixed(4)}° N · {location.longitude.toFixed(4)}° E
              </p>
            )}

            {loading && (
              <div role="status" className="space-y-4 py-5">
                <p className="text-sm font-medium">Scoring this coordinate…</p>
                <div className="h-20 animate-pulse rounded-lg bg-muted" />
                <div className="h-36 animate-pulse rounded-lg bg-muted" />
              </div>
            )}

            {noImagery && (
              <div className="mt-6 rounded-md border border-dashed border-input bg-muted p-5">
                <ShieldAlert size={28} className="mb-4 text-muted-foreground" />
                <h3 className="text-lg font-semibold" data-testid="scope-message">
                  No imagery at this coordinate
                </h3>
                <p className="mt-3 text-sm leading-6 text-muted-foreground">
                  The served mosaic has no pixels here, so no score is produced. That is missing
                  data, not an absence of manganese.
                </p>
              </div>
            )}
            {error && !noImagery && (
              <p role="alert" className="note mt-4">
                {error}
              </p>
            )}

            {data && (
              <>
                <div className="my-6 grid grid-cols-2 gap-3">
                  <ScoreTile label="Raw model score" value={data.rawScore} />
                  <ScoreTile label="Screened score" value={data.finalScore} tone="primary" />
                </div>
                <div className="py-1">
                  <div className="mb-2 flex items-center gap-2 text-xs font-semibold text-muted-foreground">
                    <Radar size={14} /> Interpretation
                  </div>
                  <p className="text-sm leading-6">
                    {data.finalScore === 0 && data.rawScore > 0
                      ? "A screening mask excluded this location. The zero is a policy result; the raw score beside it is what the model produced."
                      : `Screening index ${data.rawScore.toFixed(2)} on a 0–0.99 scale, for a single pixel. Values move sharply within a kilometre.`}
                  </p>
                  {data.maskDecision !== "n/a" && (
                    <p className="mt-2 text-xs leading-5 text-muted-foreground">
                      Mask decision: {data.maskDecision.replaceAll("_", " ")}.
                    </p>
                  )}
                  {data.margin !== null && (
                    <p className="mt-2 text-xs leading-5 text-muted-foreground">
                      Classifier margin {data.margin.toFixed(2)} log-odds
                      {data.rawProbability !== null
                        ? `, p ${data.rawProbability.toFixed(3)} before the Elkan-Noto adjustment`
                        : ""}
                      . The displayed score is capped at 0.99, so strong locations report the same
                      number while their margins differ.
                    </p>
                  )}
                  <p className="mt-2 text-xs leading-5 text-muted-foreground">
                    Not a recovery probability or an ore quantity.
                  </p>
                </div>

                <Tabs defaultValue="why" key={`${selected.kind}:${selected.id}`} className="mt-6">
                  <TabsList aria-label="Selection details">
                    <TabsTrigger value="why">Why?</TabsTrigger>
                    <TabsTrigger value="details">Details</TabsTrigger>
                  </TabsList>
                  <TabsContent value="why">
                    {data.drivers.length ? (
                      <ShapBarChart
                        shap={{
                          output_scale: "raw_margin",
                          explains: "underlying_classifier_before_pu_adjustment_and_masks",
                          // The backend sends the top five contributions and no
                          // base value, so the waterfall cannot be reconciled to
                          // the prediction. Zero is the neutral chart origin.
                          base_value: 0,
                          contributions: data.drivers.map((driver) => ({
                            feature: driver.feature,
                            label: driver.label,
                            value: driver.observed,
                            contribution: driver.contribution,
                          })),
                        }}
                      />
                    ) : (
                      <p className="text-sm leading-6 text-muted-foreground">
                        No contributions were returned for this coordinate.
                      </p>
                    )}
                  </TabsContent>
                  <TabsContent value="details">
                    <dl className="divide-y rounded-lg border bg-surface text-sm">
                      {mine && (
                        <>
                          <div className="flex justify-between gap-4 px-4 py-3">
                            <dt className="text-muted-foreground">Coordinate confidence</dt>
                            <dd className="text-right">
                              {mine.coordinate_confidence.replaceAll("_", "-")}
                            </dd>
                          </div>
                          <div className="flex justify-between gap-4 px-4 py-3">
                            <dt className="text-muted-foreground">Source</dt>
                            <dd className="max-w-52 text-right">
                              {mine.coordinate_source_url ? (
                                <a
                                  className="underline underline-offset-4"
                                  href={mine.coordinate_source_url}
                                  target="_blank"
                                  rel="noreferrer"
                                >
                                  {mine.coordinate_source}
                                </a>
                              ) : (
                                mine.coordinate_source
                              )}
                            </dd>
                          </div>
                          <div className="flex justify-between gap-4 px-4 py-3">
                            <dt className="text-muted-foreground">Mine type</dt>
                            <dd>{mine.mine_type}</dd>
                          </div>
                        </>
                      )}
                      {target && (
                        <>
                          <div className="flex justify-between gap-4 px-4 py-3">
                            <dt className="text-muted-foreground">Rank</dt>
                            <dd>
                              {target.rank} of the greenfield shortlist
                            </dd>
                          </div>
                          <div className="flex justify-between gap-4 px-4 py-3">
                            <dt className="text-muted-foreground">Neighbourhood</dt>
                            <dd>{target.neighbourhood_score.toFixed(2)} mean of adjacent cells</dd>
                          </div>
                          <div className="flex justify-between gap-4 px-4 py-3">
                            <dt className="text-muted-foreground">Coordinate precision</dt>
                            <dd>± {target.precision_m} m</dd>
                          </div>
                          <div className="flex justify-between gap-4 px-4 py-3">
                            <dt className="text-muted-foreground">Known ground</dt>
                            <dd className="text-right">Outside the 5 km occurrence buffer</dd>
                          </div>
                        </>
                      )}
                    </dl>
                    {mine?.coordinate_note && <p className="note mt-5">{mine.coordinate_note}</p>}
                    {target && (
                      <p className="note mt-5">
                        A proposal from surface reflectance and terrain, not a drill target. Nothing
                        here has been verified in the field.
                      </p>
                    )}
                  </TabsContent>
                </Tabs>

                <div className="mt-6 border-t pt-4 text-xs leading-5 text-muted-foreground">
                  <p>Scored by {data.modelVersion} at the coordinate above.</p>
                </div>
              </>
            )}
          </>
        )}
      </div>
    </aside>
  );
}
