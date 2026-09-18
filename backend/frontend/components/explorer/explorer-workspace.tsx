"use client";

import dynamic from "next/dynamic";
import { useState } from "react";
import { ArrowUpRight, Crosshair, MapPin } from "lucide-react";
import type { MaskMode } from "@/lib/contracts";
import { useExplorerStore } from "./explorer-provider";
import { SelectionInspector } from "./selection-inspector";
import { Switch } from "@/components/ui/switch";
import { cn } from "@/lib/utils";
import { useProspectivitySurface } from "@/hooks/use-prospectivity-surface";
import { useMineLocations } from "@/hooks/use-mine-locations";
import { useTopTargets } from "@/hooks/use-top-targets";
import { TargetPanel } from "./target-panel";

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
    const next: MaskMode = g && o ? "both" : g ? "geological" : o ? "occurrence_buffer" : "none";
    setMask(next);
  };
  return (
    <fieldset className="flex flex-wrap items-center gap-3 border bg-surface px-4 py-3">
      <legend className="sr-only">Screening masks</legend>
      <span className="mr-1 text-xs font-semibold text-muted-foreground">Masks</span>
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

export function ExplorerWorkspace() {
  const mask = useExplorerStore((s) => s.activeMask);
  const selected = useExplorerStore((s) => s.selected);
  const select = useExplorerStore((s) => s.select);
  const [mapNotice, setMapNotice] = useState<string | null>(null);

  const prospectivity = useProspectivitySurface(mask);
  const mineState = useMineLocations();
  const targetState = useTopTargets();
  const targets = targetState.targets?.targets ?? [];

  return (
    <div className="survey-page">
      <div className="explorer-page-heading">
        <div>
          <p className="app-kicker">02 / EXPLORER</p>
          <h1 id="explorer-heading">Prospectivity Explorer</h1>
          <p>
            Where MOIL mines today, and where the model says to look next — on one surface, with
            the evidence behind each score.
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
            <p className="mt-2 text-[11px] leading-4 text-metadata">
              Masks filter the surface and every score beneath it. Geological keeps Precambrian
              basement; the 5km buffer keeps only ground near a confirmed occurrence, which
              excludes the greenfield targets by definition.
            </p>
            <div className="mt-3">
              <MaskToggleGroup />
            </div>
          </div>
          <TargetPanel
            list={targetState.targets}
            loading={targetState.loading}
            error={targetState.error}
          />
          <SelectionInspector mines={mineState.mines} targets={targets} />
        </section>
        <section className="survey-map-column paper-panel" aria-label="Sausar map, mines and targets">
          <div className="survey-map-toolbar">
            <div>
              <h2 className="text-sm font-semibold">Sausar Belt — prospectivity</h2>
              <p className="mt-1 text-[11px] text-metadata">
                {prospectivity.origin === "fixture"
                  ? "Synthetic overlay"
                  : `Live surface${prospectivity.cached ? " · cached" : ""}${prospectivity.cellsScored !== null ? ` · ${prospectivity.cellsScored} cells scored` : ""}${prospectivity.cellsNoData ? ` · ${prospectivity.cellsNoData} no-data` : ""}`}{" "}
                · {mask.replaceAll("_", " ")} masks · {mineState.mines.length} mines ·{" "}
                {targets.length} model targets
              </p>
            </div>
          </div>
          <div className="map-surface relative">
            <MapCanvas
              mines={mineState.mines}
              targets={targets}
              activeMask={mask}
              surface={prospectivity.surface}
              selected={selected}
              onSelect={(selection) => {
                select(selection);
                setMapNotice(null);
              }}
              onUnmappedClick={() =>
                setMapNotice(
                  "Scoring an arbitrary coordinate needs a point query. Choose a mine or a model target to inspect one.",
                )
              }
            />
            {/* The backend documents 5s warm / 45s cold for /prospectivity/heatmap.
              Without this the map reads as hung on a cold first paint. */}
            {prospectivity.loading && (
              <div role="status" className="map-surface-status">
                <span className="map-surface-spinner" aria-hidden="true" />
                Scoring the prospectivity grid… first request after an API restart can take up to
                45 seconds.
              </div>
            )}
            {prospectivity.error && (
              <div role="alert" className="map-surface-status map-surface-status-error">
                Prospectivity surface unavailable — {prospectivity.error}. Mine and target markers
                still work.
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
                MOIL mines · {String(mineState.mines.length).padStart(2, "0")}
              </h2>
              <span className="text-[10px] text-metadata">Select to inspect</span>
            </div>
            {mapNotice && (
              <p role="status" className="note mb-3">
                {mapNotice}
              </p>
            )}
            {mineState.loading && (
              <p role="status" className="note mb-3">
                Loading the mine roster…
              </p>
            )}
            {mineState.error && (
              <p role="alert" className="note mb-3">
                Mine roster unavailable — {mineState.error}
              </p>
            )}
            <ul className="grid grid-cols-1 gap-px bg-border sm:grid-cols-2">
              {mineState.mines.map((mine) => {
                const active = selected?.kind === "mine" && selected.id === mine.name;
                return (
                  <li key={mine.name}>
                    <button
                      data-testid={`mine-${mine.name.replaceAll(" ", "-").toLowerCase()}`}
                      aria-pressed={active}
                      onClick={() => {
                        select({ kind: "mine", id: mine.name });
                        setMapNotice(null);
                      }}
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
              Coordinates are cited in docs/moil_coordinate_sources.md; confidence is the
              researcher&apos;s, not the model&apos;s.
            </p>
          </div>
        </section>
      </div>
      <footer className="mt-3 flex flex-wrap justify-between gap-2 text-[10px] text-metadata">
        <span>Sausar Belt · gondite geology · screening indices, not reserves</span>
        <span>Model surface · prospectivity_v6</span>
      </footer>
    </div>
  );
}
