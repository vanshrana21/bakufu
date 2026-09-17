"use client";

import dynamic from "next/dynamic";
import { useMemo, useState } from "react";
import { ArrowUpRight, Diamond, MapPin, Search } from "lucide-react";
import { DEMO_SITES, isGhostReserveCandidate } from "@/fixtures/predictions";
import type { MaskMode } from "@/lib/contracts";
import { useExplorerStore } from "./explorer-provider";
import { SiteInspector } from "./site-inspector";
import { InsetBoundary } from "@/components/shell/inset-boundary";
import { Switch } from "@/components/ui/switch";
import { Button } from "@/components/ui/button";
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

export function GhostReserveToggle() {
  const checked = useExplorerStore((s) => s.ghostOnly);
  const change = useExplorerStore((s) => s.setGhostOnly);
  return (
    <div
      className={cn(
        "ghost-control flex min-w-0 items-center justify-between gap-4 transition-colors",
        checked ? "border-oxide bg-oxide-soft" : "bg-surface",
      )}
    >
      <div className="flex items-center gap-3">
        <Diamond size={18} className="shrink-0 text-oxide" aria-hidden="true" />
        <div>
          <label
            htmlFor="ghost-reserves"
            className="cursor-pointer font-semibold text-foreground"
          >
            Ghost Reserves
          </label>
          <p className="mt-0.5 text-muted-foreground">
            Waste and slag inside 5km buffer
          </p>
        </div>
      </div>
      <div className="flex items-center gap-2">
        <span aria-hidden="true" className="text-xs font-medium text-oxide">
          {checked ? "On" : "Off"}
        </span>
        <Switch
          id="ghost-reserves"
          className="data-[state=checked]:bg-oxide"
          checked={checked}
          onCheckedChange={change}
          aria-describedby="ghost-description"
        />
      </div>
    </div>
  );
}
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

export function ExplorerWorkspace() {
  const ghostOnly = useExplorerStore((s) => s.ghostOnly);
  const mask = useExplorerStore((s) => s.activeMask);
  const selectedId = useExplorerStore((s) => s.selectedSiteId);
  const select = useExplorerStore((s) => s.selectSite);
  const [query, setQuery] = useState("");
  const [mapNotice, setMapNotice] = useState<string | null>(null);
  // GHOST RESERVE INTEGRATION: filter waste/slag AND 5km membership, independent
  // of the mask switches. Both map and site list consume this exact collection.
  const visibleSites = useMemo(
    () =>
      DEMO_SITES.filter(
        (site) =>
          site.scope_status === "in_scope" &&
          (!ghostOnly || isGhostReserveCandidate(site)),
      ),
    [ghostOnly],
  );
  const prospectivity = useProspectivitySurface(visibleSites, mask);
  const searchResults = useMemo(
    () =>
      query.trim()
        ? DEMO_SITES.filter((site) =>
            site.name.toLowerCase().includes(query.trim().toLowerCase()),
          )
        : [],
    [query],
  );
  const choose = (id: string) => {
    select(id);
    setQuery("");
    setMapNotice(null);
  };
  const selectSearch = (id: string) => {
    const site = DEMO_SITES.find((s) => s.id === id);
    if (!site) return;
    // Named out-of-scope results must remain inspectable even in Ghost mode.
    // They bypass no model gate: the mock/API returns null scores before inference.
    if (
      site.scope_status === "in_scope" &&
      ghostOnly &&
      !isGhostReserveCandidate(site)
    ) {
      setMapNotice(
        "This site is outside the Ghost Reserve filter. Turn Ghost Reserves off to inspect it.",
      );
      setQuery("");
      return;
    }
    choose(id);
  };
  return (
    <div className="survey-page">
      <div className="explorer-page-heading">
        <div>
          <p className="app-kicker">02 / EXPLORER</p>
          <h1 id="explorer-heading">Prospectivity Explorer</h1>
          <p>
            Screen historical material against model evidence and geological
            constraints.
          </p>
        </div>
        <p className="explorer-mode-label">
          <Diamond size={14} aria-hidden="true" /> Ghost Reserve screening ·
          Sausar Belt · validated scope
        </p>
      </div>
      <div className="survey-grid">
        <section
          className="survey-left paper-panel"
          aria-label="Screening controls and site evidence"
        >
          <div className="survey-intro">
            <p className="section-label">Survey controls</p>
            <GhostReserveToggle />
            <p
              id="ghost-description"
              className="mt-2 text-[11px] leading-4 text-metadata"
            >
              Waste or slag inside the 5km occurrence buffer. Synthetic
              inventory; assays and environmental review pending. Not a claim of
              measured ore.
            </p>
            <div className="mt-3">
              <MaskToggleGroup />
            </div>
          </div>
          <InsetBoundary label="Site inspector">
            <SiteInspector />
          </InsetBoundary>
        </section>
        <section
          className="survey-map-column paper-panel"
          aria-label="Sausar map and screening locations"
        >
          <div className="survey-map-toolbar">
            <div>
              <h2 className="text-sm font-semibold">
                Sausar Belt — prospectivity
              </h2>
              <p className="mt-1 text-[11px] text-metadata">
                {prospectivity.origin === "fixture"
                  ? "Synthetic overlay"
                  : `Live surface${prospectivity.cached ? " · cached" : ""}${prospectivity.cellsScored !== null ? ` · ${prospectivity.cellsScored} cells scored` : ""}${prospectivity.cellsNoData ? ` · ${prospectivity.cellsNoData} no-data` : ""}`}{" "}
                · {mask.replaceAll("_", " ")} masks · {visibleSites.length}{" "}
                locations
              </p>
            </div>
            <div className="relative z-20 w-full sm:w-72">
              <form
                onSubmit={(event) => {
                  event.preventDefault();
                  if (searchResults[0]) selectSearch(searchResults[0].id);
                }}
                className="flex items-center gap-2 border border-input bg-surface px-3"
              >
                <Search
                  size={15}
                  className="shrink-0 text-muted-foreground"
                  aria-hidden="true"
                />
                <input
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === "Escape") setQuery("");
                  }}
                  aria-label="Search fixture sites, Sandur or Bonai"
                  aria-controls="site-search-results"
                  placeholder="Search a site or belt…"
                  className="h-10 w-full min-w-0 bg-transparent text-xs outline-none"
                  autoComplete="off"
                />
              </form>
              {query.trim() && (
                <div
                  id="site-search-results"
                  className="absolute inset-x-0 top-full mt-1 border bg-surface p-1 shadow-md"
                >
                  <p className="px-3 py-2 text-xs text-muted-foreground">
                    Fixture search · not a global geocoder
                  </p>
                  {searchResults.length ? (
                    searchResults.map((site) => (
                      <button
                        key={site.id}
                        className="flex w-full items-center justify-between gap-3 px-3 py-3 text-left text-sm hover:bg-muted"
                        onClick={() => selectSearch(site.id)}
                      >
                        <span>{site.name}</span>
                        <span className="text-xs text-muted-foreground">
                          {site.scope_status === "out_of_scope"
                            ? "Outside scope"
                            : "Inspect"}
                        </span>
                      </button>
                    ))
                  ) : (
                    <p className="p-3 text-sm">
                      No fixture found. Scope has not been inferred.
                    </p>
                  )}
                </div>
              )}
            </div>
          </div>
          <div className="map-surface relative">
            <InsetBoundary label="Prospectivity map">
              <MapCanvas
                sites={visibleSites}
                activeMask={mask}
                surface={prospectivity.surface}
                selectedSiteId={selectedId}
                onSelect={choose}
                onUnmappedClick={() =>
                  setMapNotice(
                    "Arbitrary point queries require the live scope and prediction API. Choose a supplied fixture to continue.",
                  )
                }
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
                Prospectivity surface unavailable — {prospectivity.error}. Site
                markers and the list below still work.
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
                {ghostOnly ? "Ghost Reserve candidates" : "Screening locations"}{" "}
                · {String(visibleSites.length).padStart(2, "0")}
              </h2>
              <span className="text-[10px] text-metadata">
                Select to inspect
              </span>
            </div>
            {mapNotice && (
              <p role="status" className="note mb-3">
                {mapNotice}
              </p>
            )}
            <ul className="grid grid-cols-1 gap-px bg-border sm:grid-cols-2">
              {visibleSites.map((site) => (
                <li key={site.id}>
                  <button
                    data-testid={`site-${site.id}`}
                    aria-pressed={selectedId === site.id}
                    onClick={() => choose(site.id)}
                    className={cn(
                      "flex w-full items-center gap-2 px-3 py-2.5 text-left text-xs transition-colors hover:bg-muted",
                      selectedId === site.id
                        ? "bg-[var(--primary-soft)]"
                        : "bg-surface",
                    )}
                  >
                    <span className="shrink-0">
                      {site.asset_type === "diagnostic_point" ? (
                        <MapPin
                          size={13}
                          className="text-metadata"
                          aria-hidden="true"
                        />
                      ) : (
                        <Diamond
                          size={13}
                          className="text-oxide"
                          aria-hidden="true"
                        />
                      )}
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block truncate font-medium">
                        {site.name}
                      </span>
                      <span className="mt-0.5 block text-[10px] text-metadata">
                        {site.synthetic
                          ? "Synthetic asset"
                          : "Document diagnostic"}{" "}
                        · {site.inside_buffer ? "inside" : "outside"} 5km
                      </span>
                    </span>
                    <span className="text-right">
                      <span className="block text-[9px] text-metadata">
                        Raw
                      </span>
                      <span className="numeric font-semibold">
                        {site.raw_score?.toFixed(2) ?? "—"}
                      </span>
                    </span>
                    <ArrowUpRight
                      size={12}
                      className="shrink-0 text-metadata"
                      aria-hidden="true"
                    />
                  </button>
                </li>
              ))}
            </ul>
            <div className="mt-2 flex flex-wrap items-center gap-2">
              <span className="mr-auto text-[10px] text-metadata">
                Scope checks · no score outside validated geography
              </span>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => choose("sandur")}
              >
                Sandur
              </Button>
              <Button variant="ghost" size="sm" onClick={() => choose("bonai")}>
                Bonai
              </Button>
            </div>
          </div>
        </section>
      </div>
      <footer className="mt-3 flex flex-wrap justify-between gap-2 text-[10px] text-metadata">
        <span>
          Sausar Belt · gondite geology · waste-material transfer unvalidated
        </span>
        <span>Demonstration scenario / September 2026</span>
      </footer>
    </div>
  );
}
