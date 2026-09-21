/** A schematic of the Sausar Belt with points plotted at their true coordinates.
 *
 * Pure SVG with no hooks, so both Server Components (the Mine Fleet page) and
 * client components (the Explorer's target panel) can render it. It follows the
 * sheet's three inks: a mine is an observed place (mineral white), a target or
 * a score is a model estimate (steel). Colour is never the only cue: mines are
 * diamonds, targets are numbered circles.
 */

import s from "./mines.module.css";

export interface LocatorPoint {
  id: string;
  label: string;
  latitude: number;
  longitude: number;
  kind: "mine" | "target";
  /** Target rank, drawn inside its circle. */
  rank?: number;
  /** How strongly the model reads a mine: drawn as fill weight, never alone. */
  band?: "recognised" | "mixed" | "low" | "unscored";
}

const DEFAULT_BBOX: readonly [number, number, number, number] = [79.0, 21.3, 80.6, 22.1];
const WIDTH = 520;

export function BeltLocator({
  points,
  bbox = DEFAULT_BBOX,
  caption,
}: {
  points: readonly LocatorPoint[];
  bbox?: readonly [number, number, number, number];
  caption: string;
}) {
  const [west, south, east, north] = bbox;
  // Ground-true aspect: a degree of longitude is shorter than a degree of
  // latitude this far north, so the belt is drawn as it lies, not stretched.
  const lonScale = Math.cos((((south + north) / 2) * Math.PI) / 180);
  const height = Math.round((WIDTH * (north - south)) / ((east - west) * lonScale));
  const pad = 22;
  const padLeft = 46; // room for the latitude labels
  const x = (lon: number) => padLeft + ((lon - west) / (east - west)) * (WIDTH - padLeft - pad);
  const y = (lat: number) => pad + ((north - lat) / (north - south)) * (height - 2 * pad);

  const lons: number[] = [];
  for (let lon = Math.ceil(west * 5) / 5; lon <= east + 1e-9; lon += 0.2) lons.push(Number(lon.toFixed(1)));
  const lats: number[] = [];
  for (let lat = Math.ceil(south * 5) / 5; lat <= north + 1e-9; lat += 0.2) lats.push(Number(lat.toFixed(1)));

  const mines = points.filter((point) => point.kind === "mine");
  const targets = points.filter((point) => point.kind === "target");

  // Mines cluster (four sit within a few km of Nagpur), so each label tries the
  // right, then below-right, then the left, then above, and takes the first
  // slot that clears every label already placed.
  type Box = { x0: number; x1: number; y0: number; y1: number };
  const placed: Box[] = [];
  const labelFor = (cx: number, cy: number, text: string) => {
    const w = text.length * 5.6;
    const slots = [
      { x: cx + 9, y: cy + 3.5, anchor: "start" as const },
      { x: cx + 9, y: cy + 15, anchor: "start" as const },
      { x: cx - 9, y: cy + 3.5, anchor: "end" as const },
      { x: cx - 9, y: cy + 15, anchor: "end" as const },
      { x: cx + 9, y: cy - 8, anchor: "start" as const },
      { x: cx - 9, y: cy - 8, anchor: "end" as const },
    ];
    const boxOf = (slot: (typeof slots)[number]): Box =>
      slot.anchor === "start"
        ? { x0: slot.x, x1: slot.x + w, y0: slot.y - 9, y1: slot.y + 2 }
        : { x0: slot.x - w, x1: slot.x, y0: slot.y - 9, y1: slot.y + 2 };
    const clear = (box: Box) => placed.every((other) => box.x1 < other.x0 || box.x0 > other.x1 || box.y1 < other.y0 || box.y0 > other.y1);
    const slot = slots.find((candidate) => clear(boxOf(candidate))) ?? slots[0]!;
    placed.push(boxOf(slot));
    return slot;
  };

  return (
    <figure className={s.locator}>
      <svg viewBox={`0 0 ${WIDTH} ${height}`} role="img" aria-label={caption}>
        <rect x={padLeft} y={pad} width={WIDTH - padLeft - pad} height={height - 2 * pad} className={s.locatorFrame} />
        {lons.map((lon) => (
          <g key={`lon-${lon}`}>
            <line x1={x(lon)} x2={x(lon)} y1={pad} y2={height - pad} className={s.graticule} />
            <text x={x(lon)} y={height - pad + 14} className={s.graticuleLabel} textAnchor="middle">{lon.toFixed(1)}°E</text>
          </g>
        ))}
        {lats.map((lat) => (
          <g key={`lat-${lat}`}>
            <line x1={padLeft} x2={WIDTH - pad} y1={y(lat)} y2={y(lat)} className={s.graticule} />
            <text x={padLeft - 5} y={y(lat) + 3} className={s.graticuleLabel} textAnchor="end">{lat.toFixed(1)}°N</text>
          </g>
        ))}
        {mines.map((mine) => {
          const cx = x(mine.longitude);
          const cy = y(mine.latitude);
          const label = labelFor(cx, cy, mine.label);
          return (
            <g key={mine.id} className={s.mineMark} data-band={mine.band ?? "unscored"}>
              <title>{mine.label}</title>
              <path d={`M${cx} ${cy - 6} L${cx + 6} ${cy} L${cx} ${cy + 6} L${cx - 6} ${cy} Z`} />
              <text x={label.x} y={label.y} textAnchor={label.anchor} className={s.mineLabel}>{mine.label}</text>
            </g>
          );
        })}
        {targets.map((target) => {
          const cx = x(target.longitude);
          const cy = y(target.latitude);
          return (
            <g key={target.id} className={s.targetMark}>
              <title>{target.label}</title>
              <circle cx={cx} cy={cy} r={8} />
              <text x={cx} y={cy + 3.3} textAnchor="middle">{target.rank ?? ""}</text>
            </g>
          );
        })}
      </svg>
      <figcaption className={s.locatorCaption}>{caption}</figcaption>
    </figure>
  );
}
