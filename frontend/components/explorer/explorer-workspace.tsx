"use client";

import dynamic from "next/dynamic";
import { useCallback } from "react";
import { ArrowUpRight, Crosshair, MapPin } from "lucide-react";
import type { MaskMode, MineLocation, Target } from "@/lib/contracts";
import type { Selection } from "@/stores/explorer-store";
import { useExplorerStore } from "./explorer-provider";
import { SelectionInspector } from "./selection-inspector";
import { TargetPanel } from "./target-panel";
import { maskLabel } from "./mask-label";
import { InsetBoundary } from "@/components/shell/inset-boundary";
import { Switch } from "@/components/ui/switch";
import { cn } from "@/lib/utils";
import { useProspectivitySurface } from "@/hooks/use-prospectivity-surface";

// Next.js 14: ssr:false belongs inside this Client Component, not page.tsx.
const MapCanvas = dynamic(() => import("./map-canvas"), {
  ssr: false,
  loading: () => (
    <div
      role="status"
      className="absolute inset-0 flex items-center justify-center text-sm text-[var(--canvas-ink)] opacity-70"
    >
      Loading map workspace…
    </div>
  ),
});

export function MaskToggleGroup() {
  const mode = useExplorerStore((s) => s.activeMask);
  const setMask = useExplorerStore((s) => s.setMask);
  const geological = mode === "geological" || mode === "both";
  const occurrence = mode === "occurrence_buffer" || mode === "both";
  const update = (g: boolean, o: boolean) => {
    const next: MaskMode =
      g && o ? "both" : g ? "geological" : o ? "occurrence_buffer" : "none";
    setMask(next);
  };
  return (
    <fieldset className="flex flex-wrap items-center gap-3 border bg-surface px-4 py-3">
      <legend className="sr-only">Screening masks</legend>
      <span className="mr-1 text-xs font-semibold text-muted-foreground">
        Masks
      </span>
      <div className="flex items-center gap-2">
        <label htmlFor="geological-mask" className="text-sm">
          Geological
        </label>
        <Switch
          id="geological-mask"
          checked={geological}
          onCheckedChange={(value) => update(value, occurrence)}
        />
      </div>
      <div className="flex items-center gap-2">
        <label htmlFor="occurrence-mask" className="text-sm">
          5km buffer
        </label>
        <Switch
          id="occurrence-mask"
          checked={occurrence}
          onCheckedChange={(value) => update(geological, value)}
        />
      </div>
    </fieldset>
  );
}

/** One stable empty list, so the map does not redraw its markers on every render
 * while the targets are still on their way. */
const NO_TARGETS: readonly Target[] = [];

/** The Prospectivity Explorer: where MOIL mines today and where the model says
 * to look next, on one surface.
 *
 * Mines arrive as props, loaded on the server. The ranked targets stream into
 * the store after the page paints (components/explorer/targets-feed.tsx). Both
 * are real: cited coordinates and model output. Nothing on this page is a
 * hand-placed demonstration site.
 */
export function ExplorerWorkspace({ mines, minesError, minesOrigin }: {
  mines: readonly MineLocation[];
  minesError: string | null;
  minesOrigin: "live" | "fixture";
}) {
  const mask = useExplorerStore((s) => s.activeMask);
  const selected = useExplorerStore((s) => s.selected);
  const select = useExplorerStore((s) => s.select);
  const targetsState = useExplorerStore((s) => s.targets);
  const targets = targetsState.status === "ready" ? targetsState.list.targets : NO_TARGETS;
  const prospectivity = useProspectivitySurface(mask);
  const choose = useCallback((selection: Selection) => {
    select(selection);
  }, [select]);
  const scoreGround = useCallback((location: { latitude: number; longitude: number }) => {
    select({
      kind: "point",
      id: `${location.latitude.toFixed(5)},${location.longitude.toFixed(5)}`,
      location,
    });
  }, [select]);

  const surfaceLine = prospectivity.origin === "fixture"
    ? "No model surface without the backend"
    : `Live surface${prospectivity.cached ? " · cached" : ""}${prospectivity.cellsScored !== null ? ` · ${prospectivity.cellsScored} cells scored` : ""}${prospectivity.cellsNoData ? ` · ${prospectivity.cellsNoData} no-data` : ""}`;
  const targetsLine = targetsState.status === "ready"
    ? `${targets.length} model targets`
    : targetsState.status === "loading" ? "ranking targets…" : "targets unavailable";

  return (
    <div className="survey-page">
      <div className="explorer-page-heading">
        <div>
          <p className="app-kicker">02 / EXPLORER</p>
          <h1 id="explorer-heading">Prospectivity Explorer</h1>
          <p>
            Where MOIL mines today, and where the model says to look next — on one surface, with the evidence behind
            each score.
          </p>
        </div>
        <p className="explorer-mode-label">
          <Crosshair size={14} aria-hidden="true" /> Sausar Belt · validated scope
        </p>
      </div>
      <div className="survey-grid">
        <section
          className="survey-left paper-panel"
          aria-label="Screening controls, model targets and evidence"
        >
          <div className="survey-intro">
            <p className="section-label">Survey controls</p>
            <p className="text-[11px] leading-4 text-metadata">
              Masks filter the surface and every score beneath it. Geological keeps Precambrian basement; the 5km
              buffer keeps only ground near a confirmed occurrence, which excludes the greenfield targets by
              definition.
            </p>
            <div className="mt-3">
              <MaskToggleGroup />
            </div>
          </div>
          <TargetPanel />
          <InsetBoundary label="Selection inspector">
            <SelectionInspector mines={mines} targets={targets} />
          </InsetBoundary>
        </section>
        <section
          className="survey-map-column paper-panel"
          aria-label="Sausar map, MOIL mines and model targets"
        >
          <div className="survey-map-toolbar">
            <div>
              <h2 className="text-sm font-semibold">
                Sausar Belt — prospectivity
              </h2>
              <p className="mt-1 text-[11px] text-metadata" data-testid="map-status-line">
                {surfaceLine} · {maskLabel(mask)} · {mines.length} mines · {targetsLine}
              </p>
            </div>
          </div>
          <div className="map-surface relative">
            <InsetBoundary label="Prospectivity map">
              <MapCanvas
                mines={mines}
                targets={targets}
                activeMask={mask}
                surface={prospectivity.surface}
                surfaceOrigin={prospectivity.origin}
                selected={selected}
                onSelect={choose}
                onUnmappedClick={scoreGround}
              />
            </InsetBoundary>
            {/* The backend documents 5s warm / 45s cold for /prospectivity/heatmap.
              Without this the map reads as hung on a cold first paint. */}
            {prospectivity.loading && (
              <div role="status" className="map-surface-status">
                <span className="map-surface-spinner" aria-hidden="true" />
                Scoring the prospectivity grid… first request after an API
                restart can take up to 45 seconds.
              </div>
            )}
            {prospectivity.error && (
              <div
                role="alert"
                className="map-surface-status map-surface-status-error"
              >
                Prospectivity surface unavailable — {prospectivity.error}. Mine
                and target markers still work.
              </div>
            )}
          </div>
          {prospectivity.note && (
            <p role="status" className="note mt-2 text-[11px]">
              {prospectivity.note}
            </p>
          )}
          <div className="survey-location-list">
            <div className="mb-2 flex items-center justify-between gap-2">
              <h2 className="text-[10px] font-semibold uppercase tracking-[1.5px] text-metadata">
                MOIL mines · {String(mines.length).padStart(2, "0")}
              </h2>
              <span className="text-[10px] text-metadata">
                Select to inspect
              </span>
            </div>
            {minesError && (
              <p role="alert" className="note mb-3">
                Mine roster unavailable — {minesError}
              </p>
            )}
            <ul className="grid grid-cols-1 gap-px bg-border sm:grid-cols-2">
              {mines.map((mine) => {
                const active = selected?.kind === "mine" && selected.id === mine.name;
                return (
                  <li key={mine.name}>
                    <button
                      data-testid={`mine-${mine.name.replaceAll(" ", "-").toLowerCase()}`}
                      aria-pressed={active}
                      onClick={() => choose({ kind: "mine", id: mine.name })}
                      className={cn(
                        "flex w-full items-center gap-2 px-3 py-2.5 text-left text-xs transition-colors hover:bg-muted",
                        active ? "bg-[var(--primary-soft)]" : "bg-surface",
                      )}
                    >
                      <span className="shrink-0">
                        <MapPin size={13} className="text-oxide" aria-hidden="true" />
                      </span>
                      <span className="min-w-0 flex-1">
                        <span className="block truncate font-medium">{mine.name}</span>
                        {/* truncate, not wrap: the district line is long enough to
                            push the confidence block out of the row. */}
                        <span className="mt-0.5 block truncate text-[10px] text-metadata">
                          {mine.district} · {mine.state} · {mine.mine_type}
                        </span>
                      </span>
                      <span className="shrink-0 whitespace-nowrap text-right">
                        <span className="block text-[9px] text-metadata">Coordinate</span>
                        <span className="numeric font-semibold">
                          {mine.coordinate_confidence.replaceAll("_", "-")}
                        </span>
                      </span>
                      <ArrowUpRight size={12} className="shrink-0 text-metadata" aria-hidden="true" />
                    </button>
                  </li>
                );
              })}
            </ul>
            <p className="mt-2 text-[10px] text-metadata">
              {minesOrigin === "live" ? "From GET /mines." : "Reference snapshot of GET /mines."} Coordinates are cited
              in backend/docs/moil_coordinate_sources.md; confidence is the researcher&apos;s, not the model&apos;s.
            </p>
          </div>
        </section>
      </div>
      <footer className="mt-3 flex flex-wrap justify-between gap-2 text-[10px] text-metadata">
        <span>Sausar Belt · gondite geology · screening indices, not reserves</span>
        <span>{prospectivity.origin === "live" ? "Model surface · live /prospectivity/heatmap" : "No backend configured"}</span>
      </footer>
    </div>
  );
}
