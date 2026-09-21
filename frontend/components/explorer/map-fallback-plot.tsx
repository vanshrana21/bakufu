import { Satellite } from "lucide-react";
import type { MineLocation, Target } from "@/lib/contracts";
import type { Selection, SelectionKind } from "@/stores/explorer-store";
import { PLOT_EXTENT, fallbackPlotPosition } from "@/lib/map/sites";
import { MINE_ICON, TARGET_ICON } from "./map-markers";

/** Shown while Mapbox loads, or instead of it when WebGL or tiles fail: a plain
 * coordinate plot where every mine and target stays selectable. */
export function MapFallbackPlot({ mines, targets, selected, onSelect, failure }: {
  mines: readonly MineLocation[];
  targets: readonly Target[];
  selected: Selection | null;
  onSelect: (selection: Selection) => void;
  failure: string | null;
}) {
  const [[west, south], [east, north]] = PLOT_EXTENT;
  const points: Array<{ kind: SelectionKind; id: string; label: string; location: MineLocation["location"] }> = [
    ...mines.map((mine) => ({ kind: "mine" as const, id: mine.name, label: mine.name, location: mine.location })),
    ...targets.map((target) => ({ kind: "target" as const, id: target.id, label: `${target.id} · ${target.label}`, location: target.location })),
  ];
  return (
    <div className="absolute inset-0 overflow-hidden bg-[var(--canvas)] text-[var(--canvas-ink)]">
      <div
        className="absolute left-[18%] right-[18%] top-[24%] bottom-[24%] border border-[var(--map-out-of-scope)]"
        aria-hidden="true"
      >
        <div className="absolute inset-x-0 top-1/2 border-t border-[var(--map-out-of-scope)]" />
        <div className="absolute inset-y-0 left-1/2 border-l border-[var(--map-out-of-scope)]" />
        <span className="absolute -left-14 -top-2 text-xs text-[var(--canvas-muted)]">{north.toFixed(2)}°</span>
        <span className="absolute -left-14 bottom-0 text-xs text-[var(--canvas-muted)]">{south.toFixed(2)}°</span>
        <span className="absolute -bottom-6 left-0 text-xs text-[var(--canvas-muted)]">{west.toFixed(2)}° E</span>
        <span className="absolute -bottom-6 right-0 text-xs text-[var(--canvas-muted)]">{east.toFixed(2)}° E</span>
      </div>
      {points.map((point) => {
        const position = fallbackPlotPosition(point);
        const active = selected?.kind === point.kind && selected.id === point.id;
        return (
          <button
            key={`${point.kind}:${point.id}`}
            type="button"
            onClick={() => onSelect({ kind: point.kind, id: point.id })}
            aria-label={`Inspect ${point.label}`}
            aria-pressed={active}
            className={`map-marker map-marker--${point.kind} absolute z-10 -translate-x-1/2 -translate-y-1/2`}
            data-selected={active}
            style={position}
          >
            <span
              className="map-marker-icon"
              // Static SVG from map-markers.ts, no data interpolated into it.
              dangerouslySetInnerHTML={{ __html: point.kind === "mine" ? MINE_ICON : TARGET_ICON }}
            />
            {active && <span className="map-marker-tag">{point.label}</span>}
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
          <span className="hidden sm:inline">· Coordinate plot of the MOIL mines and model targets</span>
        </p>
        <p className="sr-only">{failure ?? "Every mine and target remains selectable."}</p>
      </div>
    </div>
  );
}
