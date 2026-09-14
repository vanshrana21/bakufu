"use client";
import { useEffect, useRef } from "react";
import s from "./story.module.css";
import m from "./map.module.css";

type Pt = readonly [number, number];

/* The example belt, in cell units (32 × 32). An invented outline for the
 * illustration, not a surveyed boundary. */
const BELT: readonly Pt[] = [
  [0.3, 7.3], [3, 6.8], [6.5, 8.9], [10, 8.6], [13.5, 10.7], [17, 10.6], [20.5, 13.2], [24, 13.2], [27.5, 15.5], [31.4, 17.2],
  [32.2, 21.8],
  [31.4, 26.4], [27.5, 25.4], [24, 25.5], [20.5, 23.8], [17, 23.4], [13.5, 21.1], [10, 21], [6.5, 18.7], [3, 18.6], [0.3, 16.4],
  [-0.3, 11.8],
];
/* Two example contours that cross the belt. */
const CONTOURS: readonly (readonly Pt[])[] = [
  [[-1, 14], [6, 11.5], [13, 13.5], [20, 10], [27, 11.5], [33, 9]],
  [[-1, 21], [7, 19.5], [14, 22], [21, 18.5], [28, 20], [33, 17]],
];
/* Illustrative positions, clear of the two waste candidates at (9, 14) and (22, 18). */
const PLACES: readonly { name: string; at: Pt }[] = [
  { name: "Sausar", at: [4.5, 4.6] },
  { name: "Katangi", at: [24.5, 10.6] },
  { name: "Tirodi", at: [15, 25.6] },
];
const CANDIDATES: readonly Pt[] = [[9, 14], [22, 18]];

/** Catmull-Rom through the points as cubic Béziers; each segment is [start, c1, c2, end]. */
function segments(points: readonly Pt[], closed: boolean) {
  const n = points.length;
  const get = (i: number): Pt => points[closed ? (i + n) % n : Math.max(0, Math.min(n - 1, i))] ?? [0, 0];
  const out: [Pt, Pt, Pt, Pt][] = [];
  for (let i = 0; i < (closed ? n : n - 1); i++) {
    const [p0, p1, p2, p3] = [get(i - 1), get(i), get(i + 1), get(i + 2)];
    out.push([p1, [p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6], [p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6], p2]);
  }
  return out;
}
/** A smooth SVG path in units of `scale` per cell. */
function smoothPath(points: readonly Pt[], closed: boolean, scale: number) {
  const f = (p: Pt) => `${(p[0] * scale).toFixed(1)} ${(p[1] * scale).toFixed(1)}`;
  const parts = segments(points, closed);
  const start = parts[0]?.[0];
  if (!start) return "";
  return `M${f(start)}${parts.map(([, c1, c2, end]) => `C${f(c1)} ${f(c2)} ${f(end)}`).join("")}${closed ? "Z" : ""}`;
}
/** The belt outline sampled into a polygon, for testing cell centres. */
const BELT_POLYGON: Pt[] = segments(BELT, true).flatMap(([a, b, c, d]) =>
  Array.from({ length: 12 }, (_, k): Pt => {
    const t = k / 12, u = 1 - t;
    return [
      u * u * u * a[0] + 3 * u * u * t * b[0] + 3 * u * t * t * c[0] + t * t * t * d[0],
      u * u * u * a[1] + 3 * u * u * t * b[1] + 3 * u * t * t * c[1] + t * t * t * d[1],
    ];
  }));
function insideBelt(x: number, y: number) {
  let inside = false;
  for (let i = 0, j = BELT_POLYGON.length - 1; i < BELT_POLYGON.length; j = i++) {
    const [xi, yi] = BELT_POLYGON[i] ?? [0, 0];
    const [xj, yj] = BELT_POLYGON[j] ?? [0, 0];
    if (yi > y !== yj > y && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) inside = !inside;
  }
  return inside;
}

/** North arrow, scale bar, contours, belt outline and place labels over the field. */
function MapFurniture() {
  const u = 10; // viewBox units per cell
  return (
    <svg className={m.furniture} viewBox="0 0 320 320" aria-hidden="true">
      {CONTOURS.map((line, i) => <path key={i} className={m.contour} d={smoothPath(line, false, u)} />)}
      <path className={m.belt} d={smoothPath(BELT, true, u)} />
      <g transform="translate(303 8)">
        <text className={m.mark} x="0" y="6" textAnchor="middle">N</text>
        <path className={m.markFill} d="M0 9 4.2 20 0 17.2-4.2 20Z" />
        <path className={m.markLine} d="M0 17.2V30" />
      </g>
      <g transform="translate(10 300)">
        <path className={m.markFill} d="M0 0h25v3H0Z" />
        <path className={m.markLine} d="M25 0.5h25v2H25ZM0-2.5V5.5M25-1.5V4.5M50-2.5V5.5" />
        <text className={m.mark} x="58" y="5">0 — 5 km, illustrative</text>
      </g>
      {PLACES.map(({ name, at: [x, y] }) => (
        <g key={name}>
          <circle className={m.placeDot} cx={x * u} cy={y * u} r="2.2" />
          <text className={m.place} x={x * u + 5} y={y * u + 2.5}>{name}</text>
        </g>
      ))}
    </svg>
  );
}

export function CellField() {
  const ref = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const canvas = ref.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    let progress = 1;
    const draw = () => {
      const width = canvas.clientWidth;
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      canvas.width = width * dpr;
      canvas.height = width * dpr;
      ctx.scale(dpr, dpr);
      ctx.clearRect(0, 0, width, width);
      const cell = width / 32;
      const colors = ["rgba(52, 21, 15, 0.1)", "rgba(52, 21, 15, 0.22)", "rgba(52, 21, 15, 0.4)", "rgba(133, 67, 30, 0.7)", "#85431E"];
      for (let y = 0; y < 32; y++)
        for (let x = 0; x < 32; x++) {
          // Cells outside the belt drop out late in the reveal, leaving the dot grid.
          const edge = !insideBelt(x + 0.5, y + 0.5);
          if (edge && progress > 0.78) continue;
          const signal =
            (Math.sin(x * 0.61 + y * 0.29) +
              Math.cos(y * 0.49 - x * 0.15) +
              2) /
            4;
          ctx.fillStyle =
            x / 32 < progress * 2
              ? (colors[Math.min(4, Math.floor(signal * 5))] ?? "rgba(52, 21, 15, 0.1)")
              : "rgba(52, 21, 15, 0.05)";
          ctx.fillRect(x * cell + 1, y * cell + 1, cell - 2, cell - 2);
          if (progress > 0.45 && (x + y * 2) % 11 < 3) {
            ctx.save();
            ctx.beginPath();
            ctx.rect(x * cell, y * cell, cell, cell);
            ctx.clip();
            ctx.strokeStyle = "#000000";
            ctx.lineWidth = 1;
            for (let i = -cell; i < cell * 2; i += 5) {
              ctx.beginPath();
              ctx.moveTo(x * cell + i, y * cell);
              ctx.lineTo(x * cell + i + cell, y * cell + cell);
              ctx.stroke();
            }
            ctx.restore();
          }
        }
      for (const [x, y] of CANDIDATES) {
        ctx.save();
        ctx.translate(x * cell, y * cell);
        ctx.rotate(Math.PI / 4);
        ctx.fillStyle = "#D39858";
        ctx.strokeStyle = "#000000";
        ctx.lineWidth = 2;
        ctx.fillRect(-6, -6, 12, 12);
        ctx.strokeRect(-6, -6, 12, 12);
        ctx.restore();
      }
    };
    const update = (event: Event) => {
      progress = (event as CustomEvent<number>).detail;
      draw();
    };
    canvas.addEventListener("field-progress", update);
    const resize = new ResizeObserver(draw);
    resize.observe(canvas);
    draw();
    return () => {
      resize.disconnect();
      canvas.removeEventListener("field-progress", update);
    };
  }, []);
  return (
    <>
      <canvas
        ref={ref}
        className={s.cellCanvas}
        data-cell-field
        role="img"
        aria-label="Illustrative 32 by 32 prospectivity field clipped to an example belt outline, with hatched exclusions, dotted cells outside the belt, two waste candidate diamonds, example place labels Sausar, Katangi and Tirodi, a north arrow and an illustrative 5 km scale bar"
      >
        Illustration: raw model scores are screened by masks. Out-of-scope cells
        have no prediction.
      </canvas>
      <MapFurniture />
    </>
  );
}
