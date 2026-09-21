"use client";

import { useEffect, useId, useRef } from "react";
import { gsap } from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import l from "./loop.module.css";

type Pt = readonly [number, number];
type Glyph = "flag" | "pencil" | "gear" | "check";

/* The turntable, in viewBox units. The ring is a floor circle seen with the
 * 0.4 slope of chapters 01-05, so its ellipse is 0.4 times as tall as wide. */
const RING = { cx: 450, cy: 306, rx: 290, ry: 116 };
/* Stations sit on the floor diagonals, leaving the column above the centre
 * free for the candidate coin. Order runs clockwise. */
const STATIONS: readonly { n: string; label: string; glyph: Glyph; angle: number; above: boolean }[] = [
  { n: "01", label: "A PERSON FLAGS IT", glyph: "flag", angle: -135, above: true },
  { n: "02", label: "WE WRITE DOWN WHY", glyph: "pencil", angle: -45, above: true },
  { n: "03", label: "THE MODEL RETRAINS", glyph: "gear", angle: 45, above: false },
  { n: "04", label: "IT PASSES OR IT WAITS", glyph: "check", angle: 135, above: false },
];
const PLATFORM = { half: 58, depth: 12 };
const PEDESTAL = { rx: 80, ry: 32, height: 30 };
const COIN = { rx: 62, ry: 24.8, thickness: 26, hover: 118 };
const TOKEN = { rx: 14, ry: 5.6, thickness: 6 };
/** Ring drawn as one path from station 01 clockwise, so progress maps to dash length. */
const RING_LENGTH = 1000;

/* Scroll: stations, then v6, then v7 assemble; afterwards the token makes one full orbit. */
const MOTION = {
  entry: { start: "top 88%", end: "center 70%" },
  /** One full orbit while the whole turntable stays in view. */
  orbit: { start: "center 70%", end: "center 35%" },
  stations: { duration: 0.3, stagger: 0.12 },
  v6: { y: 36, at: 0.45, duration: 0.3 },
  v7: { y: -26, at: 0.72, duration: 0.25 },
  /** The candidate drifts a little against the token, for depth. */
  drift: { x: 0.035, y: 0.06 },
} as const;

const num = (n: number) => String(Math.round(n * 10) / 10);
const path = (points: readonly Pt[], close = false) =>
  `M${points.map(([x, y]) => `${num(x)} ${num(y)}`).join("L")}${close ? "Z" : ""}`;
function ringPoint(angle: number): Pt {
  const a = (angle * Math.PI) / 180;
  return [RING.cx + RING.rx * Math.cos(a), RING.cy + RING.ry * Math.sin(a)];
}
/** Token position for orbit progress 0-1, starting and ending at station 01. */
const orbitPoint = (progress: number) => ringPoint((STATIONS[0]?.angle ?? -135) + 360 * progress);
/** A cylinder seen from above: its top ellipse centre, radii and thickness. */
function cylinder(cx: number, top: number, rx: number, ry: number, thickness: number) {
  return {
    side: `M${num(cx - rx)} ${num(top)}A${num(rx)} ${num(ry)} 0 0 0 ${num(cx + rx)} ${num(top)}V${num(top + thickness)}A${num(rx)} ${num(ry)} 0 0 1 ${num(cx - rx)} ${num(top + thickness)}Z`,
    top: { cx, cy: top, rx, ry },
  };
}

function StationGlyph({ kind }: { kind: Glyph }) {
  if (kind === "flag") {
    return <g className={l.glyph}><path d="M0 0V-28" /><path className={l.glyphFill} d="M0-28 18-22.5 0-17Z" /></g>;
  }
  if (kind === "pencil") {
    return <g className={l.glyph}><path d="M-9-4 7-20 12-15-4 1ZM-9-4-12 4-4 1M3-16 8-11" /></g>;
  }
  if (kind === "gear") {
    const teeth = Array.from({ length: 8 }, (_, i) => {
      const a = (i * Math.PI) / 4;
      return `M${num(Math.cos(a) * 8)} ${num(Math.sin(a) * 8)}L${num(Math.cos(a) * 12.5)} ${num(Math.sin(a) * 12.5)}`;
    }).join("");
    // data-ring: the story's scroll-linked rotation turns this gear. GSAP
    // rotates SVG about data-svg-origin, here the gear's own centre.
    return (
      <g transform="translate(0 -15)">
        <g className={l.glyph} data-ring data-svg-origin="0 0">
          <circle r="8" /><circle r="3" /><path d={teeth} />
        </g>
      </g>
    );
  }
  return <g className={l.glyph}><path d="M-11-26H11V-4H-11Z" /><path className={l.glyphStrong} d="M-6-15-1.5-10.5 7-21" /></g>;
}

/** Conceptual feedback workflow; an illustration, not a live pipeline status. */
export function LoopVisual() {
  const id = useId().replace(/:/g, "");
  const ref = useRef<SVGSVGElement>(null);

  useEffect(() => {
    const svg = ref.current;
    if (!svg) return;
    gsap.registerPlugin(ScrollTrigger);
    const media = gsap.matchMedia();
    const stations = Array.from(svg.querySelectorAll<SVGGElement>("[data-station]"));
    const token = svg.querySelector<SVGGElement>("[data-token]");
    const traveled = svg.querySelector<SVGPathElement>("[data-traveled]");
    const drift = svg.querySelector<SVGGElement>("[data-v7-drift]");
    const place = (progress: number) => {
      const [x, y] = orbitPoint(progress);
      token?.setAttribute("transform", `translate(${num(x)} ${num(y)})`);
      traveled?.setAttribute("stroke-dashoffset", num(RING_LENGTH * (1 - progress)));
      stations.forEach((station, k) => { station.dataset.lit = String(progress > k / 4 + 0.005 || progress >= 1); });
      drift?.setAttribute("transform", `translate(${num(-(x - RING.cx) * MOTION.drift.x)} ${num(-(y - RING.cy) * MOTION.drift.y)})`);
    };
    media.add("(prefers-reduced-motion: no-preference)", () => {
      const { entry, orbit, stations: fade, v6, v7 } = MOTION;
      const state = { progress: 0 };
      gsap.set(stations, { opacity: 0 });
      place(0);
      gsap.timeline({
        defaults: { ease: "power2.out" },
        scrollTrigger: { id: "bakufu-loop-entry", trigger: svg, start: entry.start, end: entry.end, scrub: 0.7, invalidateOnRefresh: true },
      })
        .fromTo(stations, { opacity: 0 }, { opacity: 1, duration: fade.duration, stagger: fade.stagger }, 0)
        .fromTo(svg.querySelector("[data-v6]"), { y: v6.y, opacity: 0 }, { y: 0, opacity: 1, duration: v6.duration }, v6.at)
        .fromTo(svg.querySelector("[data-v7]"), { y: v7.y, opacity: 0 }, { y: 0, opacity: 1, duration: v7.duration }, v7.at)
        .fromTo(token, { opacity: 0 }, { opacity: 1, duration: 0.08 }, 0.92);
      gsap.timeline({
        scrollTrigger: { id: "bakufu-loop-orbit", trigger: svg, start: orbit.start, end: orbit.end, scrub: 0.7, invalidateOnRefresh: true },
      }).fromTo(state, { progress: 0 }, { progress: 1, ease: "none", duration: 1, onUpdate: () => place(state.progress) });
      return () => place(1);
    });
    return () => media.revert();
  }, []);

  const [tokenX, tokenY] = orbitPoint(1);
  const pedestal = cylinder(RING.cx, RING.cy, PEDESTAL.rx, PEDESTAL.ry, PEDESTAL.height);
  const v6 = cylinder(RING.cx, RING.cy - COIN.thickness, COIN.rx, COIN.ry, COIN.thickness);
  const v7 = cylinder(RING.cx, RING.cy - COIN.thickness - COIN.hover, COIN.rx, COIN.ry, COIN.thickness);
  const start = ringPoint(STATIONS[0]?.angle ?? -135);
  const opposite = ringPoint((STATIONS[0]?.angle ?? -135) + 180);
  // Two half-ellipses from station 01, clockwise, closing back at 01.
  const ring = `M${num(start[0])} ${num(start[1])}A${RING.rx} ${RING.ry} 0 0 1 ${num(opposite[0])} ${num(opposite[1])}A${RING.rx} ${RING.ry} 0 0 1 ${num(start[0])} ${num(start[1])}`;

  const station = (item: (typeof STATIONS)[number], i: number) => {
    const [x, y] = ringPoint(item.angle);
    const { half, depth } = PLATFORM;
    const h = half * 0.4;
    const top: Pt[] = [[x, y - h], [x + half, y], [x, y + h], [x - half, y]];
    // Labels point outward: up or down to a knee, then away from the ring's centre.
    const side = x < RING.cx ? -1 : 1;
    const knee: Pt = [x, item.above ? y - 62 : y + h + depth + 32];
    const tail: Pt = [x + side * 18, knee[1]];
    return (
      <g key={item.n} className={l.station} data-station data-lit="true">
        <g className={l.platform}>
          <path d={path([[x - half, y], [x, y + h], [x, y + h + depth], [x - half, y + depth]], true)} fill="var(--shade-3)" />
          <path d={path([[x, y + h], [x + half, y], [x + half, y + depth], [x, y + h + depth]], true)} fill="var(--shade-2)" />
          <path d={path(top, true)} fill={`url(#${id}-plate)`} />
          <path className={l.platformGlow} d={path(top, true)} />
          <path className={l.edge} d={path([top[3] ?? [0, 0], top[2] ?? [0, 0], top[1] ?? [0, 0]])} />
          <g transform={`translate(${num(x - 10)} ${num(y - 6)})`}><StationGlyph kind={item.glyph} /></g>
        </g>
        <path className={l.leader} d={path([[x, item.above ? y - 40 : y + h + depth + 6], knee, tail])} />
        <text className={l.stationLabel} x={tail[0] + side * 6} y={knee[1] + 4} textAnchor={side < 0 ? "end" : "start"}>{`${item.n} / ${item.label}`}</text>
        <title>{`Step ${i + 1}: ${item.label.toLowerCase()}`}</title>
      </g>
    );
  };

  return (
    <svg ref={ref} className={l.scene} viewBox="0 0 900 520" role="img" aria-labelledby={`${id}-title ${id}-desc`}>
      <title id={`${id}-title`}>The feedback turntable: four steps around a current model and a waiting candidate</title>
      <desc id={`${id}-desc`}>
        Four stations sit on a ring: 01, a person flags it; 02, we write down why; 03, the model retrains; 04, it passes
        or it waits. In the centre, the current version v6 sits on a pedestal. Above it hovers a dashed outline of v7, a
        candidate that is not deployed. A small gold token travels the ring, lighting each station in turn.
      </desc>
      <defs>
        <linearGradient id={`${id}-plate`} x2="1" y2="1">
          <stop stopColor="var(--loop-ink)" stopOpacity="0.7" />
          <stop offset="0.4" stopColor="var(--loop-steel)" />
          <stop offset="1" stopColor="var(--shade-3)" />
        </linearGradient>
        <linearGradient id={`${id}-side`} x2="1" y2="0">
          <stop stopColor="var(--loop-steel)" />
          <stop offset="0.5" stopColor="var(--shade-3)" />
          <stop offset="1" stopColor="var(--ground)" />
        </linearGradient>
        <linearGradient id={`${id}-gold`} x2="0.7" y2="1">
          <stop stopColor="var(--paper)" />
          <stop offset="0.5" stopColor="var(--glow)" />
          <stop offset="1" stopColor="var(--ore)" />
        </linearGradient>
        <radialGradient id={`${id}-shadow`}>
          <stop stopColor="var(--ink)" stopOpacity="0.6" />
          <stop offset="1" stopColor="var(--ink)" stopOpacity="0" />
        </radialGradient>
      </defs>

      <ellipse className={l.shadow} cx={RING.cx} cy={RING.cy + 40} rx={RING.rx + 60} ry={RING.ry + 40} fill={`url(#${id}-shadow)`} />
      <path className={l.ring} d={ring} />
      <path className={l.traveled} data-traveled d={ring} pathLength={RING_LENGTH} strokeDasharray={RING_LENGTH} strokeDashoffset="0" />

      {STATIONS.filter((item) => item.above).map((item) => station(item, STATIONS.indexOf(item)))}

      <g data-v6>
        <ellipse className={l.shadow} cx={RING.cx} cy={RING.cy + PEDESTAL.height + 10} rx={PEDESTAL.rx + 30} ry={PEDESTAL.ry + 10} fill={`url(#${id}-shadow)`} />
        <path d={pedestal.side} fill={`url(#${id}-side)`} />
        <ellipse {...pedestal.top} fill="var(--shade-3)" />
        <path d={v6.side} fill={`url(#${id}-side)`} />
        <ellipse {...v6.top} fill={`url(#${id}-plate)`} />
        <ellipse className={l.edge} {...v6.top} />
        <text className={l.coinMark} x={RING.cx} y={v6.top.cy + 4} textAnchor="middle">v6</text>
        <path className={l.leader} d={path([[RING.cx + COIN.rx + 8, v6.top.cy + 8], [RING.cx + COIN.rx + 30, v6.top.cy + 8]])} />
        <text className={l.coinLabel} x={RING.cx + COIN.rx + 36} y={v6.top.cy + 12}>v6 / CURRENT VERSION</text>
      </g>

      <g data-v7>
        <g data-v7-drift>
          <path className={l.candidateSide} d={v7.side} />
          <ellipse className={l.candidateTop} {...v7.top} />
          <text className={l.coinMark} x={RING.cx} y={v7.top.cy + 4} textAnchor="middle">v7</text>
          <path className={l.leader} d={path([[RING.cx, v7.top.cy - COIN.ry - 6], [RING.cx, v7.top.cy - COIN.ry - 26]])} />
          <text className={l.coinLabel} x={RING.cx} y={v7.top.cy - COIN.ry - 34} textAnchor="middle">v7 / CANDIDATE</text>
        </g>
      </g>

      {STATIONS.filter((item) => !item.above).map((item) => station(item, STATIONS.indexOf(item)))}

      <g data-token transform={`translate(${num(tokenX)} ${num(tokenY)})`}>
        <circle className={l.tokenHalo} r="20" />
        <path d={cylinder(0, -TOKEN.thickness, TOKEN.rx, TOKEN.ry, TOKEN.thickness).side} fill="var(--ore)" />
        <ellipse cx="0" cy={-TOKEN.thickness} rx={TOKEN.rx} ry={TOKEN.ry} fill={`url(#${id}-gold)`} />
      </g>
    </svg>
  );
}
