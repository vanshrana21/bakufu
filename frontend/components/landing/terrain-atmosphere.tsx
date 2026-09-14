"use client";

import { useEffect, useId, useRef } from "react";
import s from "./terrain-atmosphere.module.css";

/** Contours of an invented height field: atmospheric artwork, never site data. */
function contours() {
  const cols = 90, rows = 60, stepX = 22, stepY = 24;
  const height = (x: number, y: number) =>
    1.4 * Math.exp(-((x - 160) ** 2 / 200000 + (y - 390) ** 2 / 170000)) +
    1.7 * Math.exp(-((x - 1490) ** 2 / 170000 + (y - 610) ** 2 / 250000)) +
    0.8 * Math.exp(-((x - 820) ** 2 / 360000 + (y - 1100) ** 2 / 120000)) +
    0.10 * Math.sin(x / 160 + y / 270) + 0.035 * Math.cos(x / 63 - y / 118);
  const grid = Array.from({ length: rows + 1 }, (_, y) =>
    Array.from({ length: cols + 1 }, (_, x) => height(x * stepX - 200, y * stepY - 200)));
  return Array.from({ length: 23 }, (_, level) => {
    const threshold = 0.12 + level * 0.075;
    const segments: string[] = [];
    for (let y = 0; y < rows; y++) for (let x = 0; x < cols; x++) {
      const points: [number, number][] = [[x, y], [x + 1, y], [x + 1, y + 1], [x, y + 1]];
      const crossings: [number, number][] = [];
      for (let edge = 0; edge < 4; edge++) {
        const first = points[edge], second = points[(edge + 1) % 4];
        if (!first || !second) continue;
        const [ax, ay] = first, [bx, by] = second;
        const a = grid[ay]?.[ax], b = grid[by]?.[bx];
        if (a === undefined || b === undefined) continue;
        if ((a < threshold) === (b < threshold)) continue;
        const t = (threshold - a) / (b - a);
        crossings.push([(ax + (bx - ax) * t) * stepX - 200, (ay + (by - ay) * t) * stepY - 200]);
      }
      for (let i = 0; i + 1 < crossings.length; i += 2) {
        const a = crossings[i], b = crossings[i + 1];
        if (!a || !b) continue;
        segments.push(`M${a[0].toFixed(1)} ${a[1].toFixed(1)}L${b[0].toFixed(1)} ${b[1].toFixed(1)}`);
      }
    }
    return segments.join("");
  });
}
const paths = contours();

export function TerrainAtmosphere({ variant }: { variant: "hero" | "waste" | "screening" }) {
  const root = useRef<HTMLDivElement>(null);
  const id = useId().replace(/:/g, "");
  useEffect(() => {
    const node = root.current;
    if (!node) return;
    let visible = false;
    const sync = () => { node.dataset.active = String(visible && !document.hidden); };
    const observer = new IntersectionObserver(([entry]) => { visible = entry?.isIntersecting ?? false; sync(); });
    observer.observe(node);
    document.addEventListener("visibilitychange", sync);
    return () => { observer.disconnect(); document.removeEventListener("visibilitychange", sync); };
  }, []);
  return (
    <div ref={root} className={`${s.ambient} ${s[variant]}`} data-active="false" data-terrain aria-hidden="true">
      <div className={s.light} />
      <svg viewBox="0 0 1600 1000" preserveAspectRatio="xMidYMid slice" className={s.field}>
        <defs>
          <g id={`${id}-contours`}>{paths.map((d, i) => <path key={i} d={d} />)}</g>
          <linearGradient id={`${id}-sweep`}><stop stopColor="var(--paper)" stopOpacity="0"/><stop offset="0.5" stopColor="var(--paper)"/><stop offset="1" stopColor="var(--paper)" stopOpacity="0"/></linearGradient>
          <mask id={`${id}-light`} maskUnits="userSpaceOnUse" x="-300" y="-300" width="2200" height="1600" style={{ maskType: "alpha" }}>
            <rect className={s.sweep} x="-800" y="-300" width="650" height="1600" fill={`url(#${id}-sweep)`} />
          </mask>
        </defs>
        <g className={s.land} fill="none" strokeLinejoin="round" strokeLinecap="round">
          <use href={`#${id}-contours`} stroke="#57717B" strokeWidth="1.2" opacity="0.44" />
          <use href={`#${id}-contours`} stroke="var(--glow)" strokeWidth="1.8" opacity="0.76" mask={`url(#${id}-light)`} />
        </g>
      </svg>
    </div>
  );
}
