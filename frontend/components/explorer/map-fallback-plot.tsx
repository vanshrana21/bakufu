import { Diamond, Satellite } from "lucide-react";
import type { SiteFixture } from "@/fixtures/predictions";
import { fallbackPlotPosition } from "@/lib/map/sites";

/** Shown while Mapbox loads, or instead of it when WebGL or tiles fail: a plain
 * coordinate plot where every site stays selectable. */
export function MapFallbackPlot({ sites, selectedSiteId, onSelect, failure }: {
  sites: readonly SiteFixture[];
  selectedSiteId: string | null;
  onSelect: (siteId: string) => void;
  failure: string | null;
}) {
  return (
    <div className="absolute inset-0 overflow-hidden bg-[var(--canvas)] text-[var(--canvas-ink)]">
      <div
        className="absolute left-[18%] right-[18%] top-[24%] bottom-[24%] border border-[var(--map-out-of-scope)]"
        aria-hidden="true"
      >
        <div className="absolute inset-x-0 top-1/2 border-t border-[var(--map-out-of-scope)]" />
        <div className="absolute inset-y-0 left-1/2 border-l border-[var(--map-out-of-scope)]" />
        <span className="absolute -left-14 -top-2 text-xs text-[var(--canvas-muted)]">
          21.95°
        </span>
        <span className="absolute -left-14 bottom-0 text-xs text-[var(--canvas-muted)]">
          21.45°
        </span>
        <span className="absolute -bottom-6 left-0 text-xs text-[var(--canvas-muted)]">
          79.15° E
        </span>
        <span className="absolute -bottom-6 right-0 text-xs text-[var(--canvas-muted)]">
          80.15° E
        </span>
      </div>
      {sites.map((site) => {
        const position = fallbackPlotPosition(site);
        if (!position) return null;
        const active = selectedSiteId === site.id;
        return (
          <button
            key={site.id}
            type="button"
            onClick={() => onSelect(site.id)}
            aria-label={`Inspect ${site.name}`}
            aria-pressed={active}
            className="absolute z-10 flex h-8 w-8 -translate-x-1/2 -translate-y-1/2 items-center justify-center focus-visible:outline-[var(--canvas-ink)]"
            style={position}
          >
            <span
              className={`flex h-7 w-7 items-center justify-center rounded-full ${active ? "border-2 border-[var(--canvas-ink)] bg-[var(--canvas)]" : ""}`}
            >
              {site.asset_type === "diagnostic_point" ? (
                <span className="h-3 w-3 rounded-full border border-[var(--canvas-ink)] bg-[var(--canvas-muted)]" />
              ) : (
                <Diamond
                  size={18}
                  fill="var(--map-ghost)"
                  stroke="#EACEAA"
                  strokeWidth={1.5}
                />
              )}
            </span>
            {active && (
              <span
                className={`absolute top-8 w-max max-w-48 rounded-md border border-[var(--map-out-of-scope)] bg-[var(--canvas)] px-3 py-2 text-left text-xs text-[var(--canvas-ink)] ${Number.parseFloat(position.left) > 60 ? "right-0" : "left-0"}`}
              >
                {site.name}
              </span>
            )}
          </button>
        );
      })}
      <div
        role="status"
        className="pointer-events-none absolute left-4 right-4 top-[72px] text-xs leading-5 text-[var(--canvas-muted)]"
      >
        <p className="flex items-center gap-2">
          <Satellite size={14} />
          <strong className="font-medium text-[var(--canvas-ink)]">
            {failure ? "Map rendering unavailable" : "Loading map layers"}
          </strong>
          <span className="hidden sm:inline">
            · Coordinate plot of demonstration sites
          </span>
        </p>
        <p className="sr-only">
          {failure ?? "The site selection workflow remains available."}
        </p>
      </div>
    </div>
  );
}
