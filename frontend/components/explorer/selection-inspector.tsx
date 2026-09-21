"use client";

/** Evidence for whatever the map has selected: an operating MOIL mine, or one
 * of the model's greenfield targets.
 *
 * Both selections are coordinates, so the same /predict/point call explains
 * either, under the mask the Explorer has active. Ported from the team lead's
 * Explorer (yashnimde-ship-it/Spin-off, 12ba14b and 0f99c67) onto this
 * workspace's inspector shell: score tiles, tabs, the mask panel.
 */

import { useEffect, useRef } from "react";
import { Crosshair, MapPin, Radar, ShieldAlert, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import type { MineLocation, PredictionResponse, Target } from "@/lib/contracts";
import { usePointExplanation } from "@/hooks/use-point-explanation";
import { prefersReducedMotion } from "@/lib/map/sites";
import { useExplorerStore } from "./explorer-provider";
import { ShapBarChart } from "./shap-bar-chart";
import { maskLabel } from "./mask-label";

function MaskExplanationPanel({ prediction }: { prediction: PredictionResponse }) {
  return (
    <div className="space-y-4">
      {prediction.mask_results.length === 0 && <p className="text-sm">No screening mask is active.</p>}
      {prediction.mask_results.map((r) => (
        <div key={r.mask} className="border-b pb-4">
          <div className="mb-2 flex justify-between gap-2 text-sm font-semibold">
            <span>{r.mask === "geological" ? "Geological formation" : "5km occurrence buffer"}</span>
            <span
              className={cn(
                "text-xs font-semibold",
                r.outcome === "passed" ? "text-success" : r.outcome === "excluded" ? "text-warning" : "text-metadata",
              )}
            >
              {r.outcome}
            </span>
          </div>
          <p className="text-sm leading-6 text-muted-foreground">{r.reason}</p>
          <p className="mt-2 text-xs leading-5 text-muted-foreground">{r.source}</p>
        </div>
      ))}
      <p className="note">Mask inclusion is not environmental approval or a claim of measured ore.</p>
    </div>
  );
}

function ScoreTile({ label, value, tone = "neutral" }: { label: string; value: number | null; tone?: "neutral" | "primary" }) {
  return (
    <div className={tone === "primary" ? "border-b-2 border-primary pb-4" : "border-b pb-4"}>
      <p className="text-xs font-medium text-muted-foreground">{label}</p>
      <p
        className="mt-2 text-[34px] font-semibold leading-none tracking-tight tabular-nums"
        data-kind="model"
        data-testid={label.toLowerCase().includes("raw") ? "raw-score" : "final-score"}
      >
        {value?.toFixed(2) ?? "—"}
      </p>
    </div>
  );
}

function Fact({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex justify-between gap-4 px-4 py-3">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="text-right">{children}</dd>
    </div>
  );
}

export function SelectionInspector({ mines, targets }: { mines: readonly MineLocation[]; targets: readonly Target[] }) {
  const selected = useExplorerStore((s) => s.selected);
  const mask = useExplorerStore((s) => s.activeMask);
  const select = useExplorerStore((s) => s.select);

  const mine = selected?.kind === "mine" ? (mines.find((m) => m.name === selected.id) ?? null) : null;
  const target = selected?.kind === "target" ? (targets.find((t) => t.id === selected.id) ?? null) : null;
  const location = mine?.location ?? target?.location ?? null;
  const { data, loading, error, unavailable } = usePointExplanation(location, mask);

  // The inspector sits below the target list, so a choice made on the map or in
  // the mine roster would otherwise land out of sight. A choice made in the
  // target list is not followed: its row has just opened where the user is looking.
  const panel = useRef<HTMLElement>(null);
  const selectionKey = selected ? `${selected.kind}:${selected.id}` : null;
  useEffect(() => {
    if (!selectionKey || document.activeElement?.closest(".target-panel")) return;
    panel.current?.scrollIntoView({ block: "nearest", behavior: prefersReducedMotion() ? "auto" : "smooth" });
  }, [selectionKey]);

  return (
    <aside ref={panel} className="inspector" aria-label="Selection inspector" aria-busy={loading}>
      <div className="flex h-14 items-center justify-between border-b px-5">
        <span className="text-xs font-semibold text-muted-foreground">Selection inspector</span>
        <Button variant="ghost" size="icon" aria-label="Clear selection" onClick={() => select(null)}>
          <X size={16} />
        </Button>
      </div>
      <div className="p-5" aria-live="polite">
        {!location && (
          <div className="py-14 text-center">
            <div className="mx-auto mb-5 flex h-14 w-14 items-center justify-center rounded-xl bg-muted">
              <MapPin size={25} className="text-muted-foreground" />
            </div>
            <h2 className="text-lg font-semibold">Inspect a location</h2>
            <p className="mx-auto mt-3 max-w-64 text-sm leading-6 text-muted-foreground">
              Choose a MOIL mine or a model target, on the map or in the lists, to see its score and the features behind it.
            </p>
          </div>
        )}

        {location && (
          <>
            <div className="mb-4 flex items-center justify-between gap-3">
              <span className="flex items-center gap-2 text-xs font-semibold text-muted-foreground">
                {mine ? <MapPin size={14} aria-hidden="true" /> : <Crosshair size={14} aria-hidden="true" />}
                {mine ? "Operating MOIL mine" : `Model target · rank ${target!.rank}`}
              </span>
              <span className="text-xs text-metadata">{maskLabel(mask)}</span>
            </div>
            <h2 className="text-[24px] font-semibold leading-tight tracking-tight">{mine?.name ?? target!.id}</h2>
            <p className="mt-2 text-xs text-muted-foreground">
              {mine ? `${mine.district}, ${mine.state} · ${mine.mine_type}` : target!.label}
            </p>
            <p className="mt-2 font-mono text-xs tabular-nums text-muted-foreground">
              {location.latitude.toFixed(4)}° N · {location.longitude.toFixed(4)}° E
            </p>

            {loading && (
              <div role="status" className="space-y-4 py-5">
                <p className="text-sm font-medium">Scoring this coordinate…</p>
                <div className="h-20 animate-pulse rounded-lg bg-muted" />
                <div className="h-36 animate-pulse rounded-lg bg-muted" />
              </div>
            )}
            {unavailable && <p role="note" className="note mt-4">{unavailable}</p>}
            {error && <p role="alert" className="note mt-4">{error}</p>}

            {data && data.scope_status !== "in_scope" && (
              <div className="mt-6 rounded-md border border-dashed border-input bg-muted p-5">
                <ShieldAlert size={28} className="mb-4 text-muted-foreground" />
                <h3 className="text-lg font-semibold" data-testid="scope-message">{data.scope_reason}</h3>
                <p className="mt-3 text-sm leading-6 text-muted-foreground">{data.interpretation}</p>
              </div>
            )}

            {data && data.scope_status === "in_scope" && (
              <>
                <div className="my-6 grid grid-cols-2 gap-3">
                  <ScoreTile label="Raw model score" value={data.raw_score} />
                  <ScoreTile label="Screened score" value={data.final_score} tone="primary" />
                </div>
                <div className="py-1">
                  <div className="mb-2 flex items-center gap-2 text-xs font-semibold text-muted-foreground">
                    <Radar size={14} /> Interpretation
                  </div>
                  <p className="text-sm leading-6">{data.interpretation}</p>
                  {data.mask_results.some((result) => result.outcome === "excluded") && (
                    <p className="mt-2 flex items-center gap-2 text-xs font-semibold text-warning">
                      <ShieldAlert size={14} />
                      Excluded by mask · zero is a policy result
                    </p>
                  )}
                  {data.model_margin !== null && (
                    <p className="mt-2 text-xs leading-5 text-muted-foreground" data-testid="model-margin">
                      Classifier margin {data.model_margin.toFixed(2)} log-odds
                      {data.raw_probability !== null ? `, p ${data.raw_probability.toFixed(3)} before the Elkan-Noto adjustment` : ""}.
                      The displayed score is capped at 0.99, so strong locations share it while their margins differ.
                    </p>
                  )}
                </div>

                <Tabs defaultValue="why" key={`${selected!.kind}:${selected!.id}`} className="mt-6">
                  <TabsList aria-label="Selection details">
                    <TabsTrigger value="why">Why?</TabsTrigger>
                    <TabsTrigger value="constraints">Constraints</TabsTrigger>
                    <TabsTrigger value="details">Details</TabsTrigger>
                  </TabsList>
                  <TabsContent value="why">
                    {data.shap ? (
                      <ShapBarChart shap={data.shap} />
                    ) : (
                      <p className="text-sm leading-6 text-muted-foreground">No feature contributions were returned for this coordinate.</p>
                    )}
                  </TabsContent>
                  <TabsContent value="constraints">
                    <MaskExplanationPanel prediction={data} />
                  </TabsContent>
                  <TabsContent value="details">
                    <dl className="divide-y rounded-lg border bg-surface text-sm">
                      {mine && (
                        <>
                          <Fact label="Coordinate confidence">{mine.coordinate_confidence.replaceAll("_", "-")}</Fact>
                          <Fact label="Source">
                            {mine.coordinate_source_url ? (
                              <a className="underline underline-offset-4" href={mine.coordinate_source_url} target="_blank" rel="noreferrer">
                                {mine.coordinate_source}
                              </a>
                            ) : mine.coordinate_source}
                          </Fact>
                          <Fact label="Mine type">{mine.mine_type}</Fact>
                        </>
                      )}
                      {target && (
                        <>
                          <Fact label="Rank">{target.rank} of the greenfield shortlist</Fact>
                          <Fact label="Neighbourhood">{target.neighbourhood_score.toFixed(2)} mean of adjacent cells</Fact>
                          <Fact label="Coordinate precision">± {target.precision_m} m</Fact>
                          <Fact label="Known ground">Outside the 5 km occurrence buffer</Fact>
                        </>
                      )}
                    </dl>
                    {mine?.coordinate_note && <p className="note mt-5">{mine.coordinate_note}</p>}
                    {target && (
                      <p className="note mt-5">
                        A proposal from surface reflectance and terrain, not a drill target. Nothing here has been verified in the field.
                      </p>
                    )}
                  </TabsContent>
                </Tabs>
              </>
            )}

            {data && (
              <div className="mt-6 border-t pt-4 text-xs leading-5 text-muted-foreground">
                <p>{data.provenance.source}</p>
              </div>
            )}
          </>
        )}
      </div>
    </aside>
  );
}
