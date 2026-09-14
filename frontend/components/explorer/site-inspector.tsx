"use client";
import {
  CheckCircle2,
  FlaskConical,
  MapPin,
  Radar,
  ShieldAlert,
  X,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { usePrediction } from "@/hooks/use-prediction";
import { useExplorerStore } from "./explorer-provider";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ShapBarChart } from "./shap-bar-chart";
import type { PredictionResponse } from "@/lib/contracts";

export function MaskExplanationPanel({
  prediction,
}: {
  prediction: PredictionResponse;
}) {
  return (
    <div className="space-y-4">
      {prediction.mask_results.length === 0 && (
        <p className="text-sm">No screening mask is active.</p>
      )}
      {prediction.mask_results.map((r) => (
        <div key={r.mask} className="border-b pb-4">
          <div className="mb-2 flex justify-between gap-2 text-sm font-semibold">
            <span>
              {r.mask === "geological"
                ? "Geological formation"
                : "5km occurrence buffer"}
            </span>
            <span
              className={cn(
                "text-xs font-semibold",
                r.outcome === "passed"
                  ? "text-success"
                  : r.outcome === "excluded"
                    ? "text-warning"
                    : "text-metadata",
              )}
            >
              {r.outcome}
            </span>
          </div>
          <p className="text-sm leading-6 text-muted-foreground">{r.reason}</p>
          <p className="mt-2 text-xs leading-5 text-muted-foreground">
            {r.source}
          </p>
        </div>
      ))}
      <p className="note">
        Mask inclusion is not environmental approval. Environmental checks and
        waste assay results are not supplied.
      </p>
    </div>
  );
}

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
    <div
      className={
        tone === "primary" ? "border-b-2 border-primary pb-4" : "border-b pb-4"
      }
    >
      <p className="text-xs font-medium text-muted-foreground">{label}</p>
      <p
        className="mt-2 text-[34px] font-semibold leading-none tracking-tight"
        data-testid={
          label.toLowerCase().includes("raw") ? "raw-score" : "final-score"
        }
      >
        {value?.toFixed(2) ?? "—"}
      </p>
    </div>
  );
}

export function SiteInspector() {
  const { data, loading, error, selected } = usePrediction();
  const select = useExplorerStore((s) => s.selectSite);
  return (
    <aside
      className="inspector"
      aria-label="Site inspector"
      aria-busy={loading}
    >
      <div className="flex h-14 items-center justify-between border-b px-5">
        <span className="text-xs font-semibold text-muted-foreground">
          Selection inspector
        </span>
        <Button
          variant="ghost"
          size="icon"
          aria-label="Clear selection"
          onClick={() => select(null)}
        >
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
              Choose a site from the map or site list to review its evidence,
              masks and explanation.
            </p>
          </div>
        )}
        {loading && (
          <div role="status" className="space-y-4 py-5">
            <p className="text-sm font-medium">Loading selected evidence...</p>
            <div className="h-20 animate-pulse rounded-lg bg-muted" />
            <div className="h-36 animate-pulse rounded-lg bg-muted" />
            <div className="h-24 animate-pulse rounded-lg bg-muted" />
          </div>
        )}
        {error && (
          <p role="alert" className="note">
            {error}
          </p>
        )}
        {data && (
          <>
            <div className="mb-4 flex items-center justify-between gap-3">
              <div className="flex items-center gap-2 text-xs font-semibold text-muted-foreground">
                <FlaskConical size={14} /> Fixture evidence
              </div>
              {data.scope_status === "in_scope" && (
                <span className="flex items-center gap-1.5 text-xs font-medium text-info">
                  <CheckCircle2 size={13} /> Geographic scope
                </span>
              )}
            </div>
            <h2 className="text-[24px] font-semibold leading-tight tracking-tight">
              {data.asset.name}
            </h2>
            {data.location && (
              <p className="mt-2 text-xs text-muted-foreground">
                {data.location.latitude.toFixed(4)}° N ·{" "}
                {data.location.longitude.toFixed(4)}° E
              </p>
            )}
            {data.scope_status === "in_scope" && (
              <p className="mt-3 flex justify-between border-y py-2 text-xs">
                <span className="text-metadata">Assay status</span>
                <strong className="font-medium">
                  {data.asset.assay_status.replaceAll("_", " ")}
                </strong>
              </p>
            )}
            {/* An out-of-scope response has null scores by contract: never show 0%. */}
            {data.scope_status !== "in_scope" ? (
              <div className="mt-6 rounded-md border border-dashed border-input bg-muted p-5">
                <ShieldAlert size={28} className="mb-4 text-muted-foreground" />
                <h3
                  className="text-lg font-semibold"
                  data-testid="scope-message"
                >
                  {data.scope_status === "out_of_scope"
                    ? "Outside validated scope (Sausar Belt)"
                    : "Scope could not be established"}
                </h3>
                <p className="mt-3 text-sm leading-6 text-muted-foreground">
                  {data.interpretation}
                </p>
              </div>
            ) : (
              <>
                <div className="my-6 grid grid-cols-2 gap-3">
                  <ScoreTile label="Raw model score" value={data.raw_score} />
                  <ScoreTile
                    label="Screened score"
                    value={data.final_score}
                    tone="primary"
                  />
                </div>
                <div className="py-1">
                  <div className="mb-2 flex items-center gap-2 text-xs font-semibold text-muted-foreground">
                    <Radar size={14} /> Interpretation
                  </div>
                  <p className="text-sm leading-6">{data.interpretation}</p>
                  {data.mask_results.some(
                    (mask) => mask.outcome === "excluded",
                  ) && (
                    <p className="mt-2 flex items-center gap-2 text-xs font-semibold text-warning">
                      <ShieldAlert size={14} />
                      Excluded by mask · zero is a policy result
                    </p>
                  )}
                  <p className="mt-2 text-xs leading-5 text-muted-foreground">
                    Score is not recovery probability or ore quantity.
                  </p>
                </div>
                <Tabs
                  defaultValue="evidence"
                  key={data.asset.id}
                  className="mt-6"
                >
                  <TabsList aria-label="Site details">
                    <TabsTrigger value="evidence">Evidence</TabsTrigger>
                    <TabsTrigger value="why">Why?</TabsTrigger>
                    <TabsTrigger value="constraints">Constraints</TabsTrigger>
                  </TabsList>
                  <TabsContent value="evidence">
                    <dl className="divide-y rounded-lg border bg-surface text-sm">
                      <div className="flex justify-between gap-4 px-4 py-3">
                        <dt className="text-muted-foreground">Inventory</dt>
                        <dd className="text-right">
                          {data.asset.inventory_status === "synthetic"
                            ? "Synthetic demo asset"
                            : "Document diagnostic"}
                        </dd>
                      </div>
                      <div className="flex justify-between gap-4 px-4 py-3">
                        <dt className="text-muted-foreground">Assay</dt>
                        <dd>{data.asset.assay_status.replaceAll("_", " ")}</dd>
                      </div>
                      <div className="flex justify-between gap-4 px-4 py-3">
                        <dt className="text-muted-foreground">
                          5km membership
                        </dt>
                        <dd>{data.asset.occurrence_buffer_membership}</dd>
                      </div>
                    </dl>
                    <p className="note mt-5">
                      {data.asset.asset_type === "slag_heap"
                        ? "Processed slag differs from the geology used for training. Geographic inclusion does not validate material recoverability."
                        : "Ghost Reserve examples demonstrate the workflow. The project state contains no verified waste-dump inventory."}
                    </p>
                  </TabsContent>
                  <TabsContent value="why">
                    {data.shap ? (
                      <ShapBarChart shap={data.shap} />
                    ) : (
                      <p className="text-sm leading-6 text-muted-foreground">
                        No numeric SHAP payload was provided for this
                        diagnostic. Connect the backend explanation endpoint to
                        display it.
                      </p>
                    )}
                  </TabsContent>
                  <TabsContent value="constraints">
                    <MaskExplanationPanel prediction={data} />
                  </TabsContent>
                </Tabs>
              </>
            )}
            <div className="mt-6 border-t pt-4 text-xs leading-5 text-muted-foreground">
              <p>{data.provenance.source}</p>
              <p className="mt-2">Interface: {data.provenance.model_version}</p>
            </div>
          </>
        )}
      </div>
    </aside>
  );
}
