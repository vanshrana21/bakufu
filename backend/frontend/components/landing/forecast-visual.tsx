"use client";

import { useEffect, useId, useRef, useState } from "react";
import { gsap } from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import f from "./forecast.module.css";

type Pt = readonly [number, number];

/* One projection for the whole scene, with the 0.4 slope of chapters 01-03:
 * time t runs right and up, depth d runs right and down, height z runs up. */
const SLOPE = 0.4;
const ORIGIN: Pt = [40, 530];
const P = (t: number, d: number, z: number): Pt => [ORIGIN[0] + t + d, ORIGIN[1] - SLOPE * t + SLOPE * d - z];
const num = (n: number) => String(Math.round(n * 10) / 10);
const path = (points: readonly Pt[], close = false) =>
  `M${points.map(([x, y]) => `${num(x)} ${num(y)}`).join("L")}${close ? "Z" : ""}`;

/* A schematic trajectory in scene units, not production data. */
const SCENE = {
  view: [940, 560],
  step: 40,
  depth: 80,
  /** Heights of thin slabs, one per past month: a rising, uneven staircase. */
  actuals: [40, 62, 54, 84, 100, 126],
  slab: 16,
  futureMonths: 5,
  guess: { from: 126, to: 176 },
  /** Band half-height at today and at the far end, in scene units. */
  spread: { near: 8, far: 120 },
  band: { back: 16, mid: 40, front: 64 },
  marker: { height: 300, thickness: 6 },
  /** The coin: the ring spans 0-100%; the arc is the risk; the tick is the 25% line where risk turns medium. */
  coin: { cx: 770, cy: 430, rx: 130, ry: 52, depth: 24, outer: 0.84, inner: 0.6, risk: 0.32, line: 0.25 },
} as const;
const TODAY = SCENE.step * SCENE.actuals.length;
const END = TODAY + SCENE.step * SCENE.futureMonths;
const MONTHS = Array.from({ length: SCENE.futureMonths + 1 }, (_, i) => TODAY + SCENE.step * i);
const NEXT = MONTHS[1] ?? TODAY;

/* Scroll-in: steps rise one after another, the marker drops in, then the band opens. */
const MOTION = {
  rise: { y: 38, duration: 0.3, stagger: 0.05 },
  marker: { y: -70, at: 0.34, duration: 0.26 },
  bloom: { at: 0.56, duration: 0.44 },
  coin: { y: 18, at: 0.62, duration: 0.3 },
  parallax: { terrace: 14, band: -16 },
} as const;

const guessAt = (t: number) => SCENE.guess.from + ((SCENE.guess.to - SCENE.guess.from) * (t - TODAY)) / (END - TODAY);
const halfAt = (t: number, open: number) =>
  SCENE.spread.near + (open * (SCENE.spread.far - SCENE.spread.near) * (t - TODAY)) / (END - TODAY);

/** The interval wedge at a given opening, 0 (a line) to 1 (full band). */
function bandShapes(open: number) {
  const edge = (d: number, sign: 1 | -1) => MONTHS.map((t) => P(t, d, guessAt(t) + sign * halfAt(t, open)));
  const { back, front } = SCENE.band;
  return {
    back: path([...edge(back, 1), ...edge(back, -1).reverse()], true),
    lid: path([...edge(back, 1), ...edge(front, 1).reverse()], true),
    front: path([...edge(front, 1), ...edge(front, -1).reverse()], true),
    upper: path(edge(front, 1)),
    lower: path(edge(front, -1)),
  };
}

function coinPoint(scale: number, fraction: number): Pt {
  const { cx, cy, rx, ry } = SCENE.coin;
  const angle = (fraction * 360 - 90) * (Math.PI / 180);
  return [cx + rx * scale * Math.cos(angle), cy + ry * scale * Math.sin(angle)];
}
function coinSector(from: number, to: number) {
  const { rx, ry, outer, inner } = SCENE.coin;
  const large = to - from > 0.5 ? 1 : 0;
  const [a, b, c, d] = [coinPoint(outer, from), coinPoint(outer, to), coinPoint(inner, to), coinPoint(inner, from)];
  return `M${num(a[0])} ${num(a[1])}A${num(rx * outer)} ${num(ry * outer)} 0 ${large} 1 ${num(b[0])} ${num(b[1])}` +
    `L${num(c[0])} ${num(c[1])}A${num(rx * inner)} ${num(ry * inner)} 0 ${large} 0 ${num(d[0])} ${num(d[1])}Z`;
}

/** Schematic forecast scene; illustrative shapes, not a dated forecast. */
export function ForecastVisual() {
  const id = useId().replace(/:/g, "");
  const ref = useRef<SVGSVGElement>(null);
  const [band, setBand] = useState(false);
  const [gauge, setGauge] = useState(false);
  const full = bandShapes(1);

  // The gauge gloss lives in the chapter text; it lights with the coin.
  useEffect(() => {
    ref.current?.closest("section")?.setAttribute("data-gauge-on", String(gauge));
  }, [gauge]);

  useEffect(() => {
    const svg = ref.current;
    if (!svg) return;
    gsap.registerPlugin(ScrollTrigger);
    const media = gsap.matchMedia();
    const shapes = {
      back: svg.querySelector("[data-band-back]"),
      lid: svg.querySelector("[data-band-lid]"),
      front: svg.querySelector("[data-band-front]"),
      upper: svg.querySelector("[data-band-upper]"),
      lower: svg.querySelector("[data-band-lower]"),
    };
    const openBand = (open: number) => {
      const next = bandShapes(open);
      (Object.keys(shapes) as (keyof typeof shapes)[]).forEach((key) => shapes[key]?.setAttribute("d", next[key]));
    };
    media.add("(prefers-reduced-motion: no-preference)", () => {
      const pick = gsap.utils.selector(svg);
      const steps = pick("[data-step]");
      const { rise, marker, bloom, coin, parallax } = MOTION;
      const bandState = { open: 0 };
      // Every step starts low, not only the first of the staggered group.
      gsap.set(steps, { y: rise.y, opacity: 0 });
      openBand(0);
      gsap.timeline({
        defaults: { ease: "power2.out" },
        scrollTrigger: {
          id: "bakufu-forecast", trigger: svg, start: "top 88%", end: "center 70%",
          scrub: 0.7, invalidateOnRefresh: true,
        },
      })
        .fromTo(pick("[data-terrace]"), { y: parallax.terrace }, { y: 0, ease: "none", duration: 1 }, 0)
        .fromTo(pick("[data-future]"), { y: parallax.band }, { y: 0, ease: "none", duration: 1 }, 0)
        .fromTo(steps, { y: rise.y, opacity: 0 }, { y: 0, opacity: 1, duration: rise.duration, stagger: rise.stagger }, 0)
        .fromTo(pick("[data-marker]"), { y: marker.y, opacity: 0 }, { y: 0, opacity: 1, duration: marker.duration }, marker.at)
        .fromTo(pick("[data-guess]"), { opacity: 0 }, { opacity: 1, duration: 0.12 }, bloom.at)
        .fromTo(bandState, { open: 0 }, { open: 1, duration: bloom.duration, ease: "power2.inOut", onUpdate: () => openBand(bandState.open) }, bloom.at)
        .fromTo(pick("[data-coin]"), { y: coin.y, opacity: 0 }, { y: 0, opacity: 1, duration: coin.duration }, coin.at);
      return () => openBand(1);
    });
    return () => media.revert();
  }, []);

  const { step, depth, actuals, slab, marker, band: bandDepth, coin } = SCENE;
  const firstStep = P(step / 2, depth / 2, actuals[0] ?? 0);
  const nextUpper = P(NEXT, bandDepth.front, guessAt(NEXT) + halfAt(NEXT, 1));
  const nextLower = P(NEXT, bandDepth.front, guessAt(NEXT) - halfAt(NEXT, 1));
  const markerTop = P(TODAY, depth / 2, marker.height);
  const bandEndTop = P(END, bandDepth.back, guessAt(END) + halfAt(END, 1));
  const lineTick = [coinPoint(coin.inner - 0.12, coin.line), coinPoint(coin.outer + 0.14, coin.line)] as const;

  return (
    <svg ref={ref} className={f.scene} viewBox={`0 0 ${SCENE.view.join(" ")}`} role="img" aria-labelledby={`${id}-title ${id}-desc`}>
      <title id={`${id}-title`}>What really happened, today, and what could happen next</title>
      <desc id={`${id}-desc`}>
        A schematic, not a dated forecast. A rising stepped terrace shows what really happened. A tall marker shows
        today, the issue date. A dashed best guess continues inside a widening band that shows where the truth usually
        lands. A coin gauge shows a 32 percent chance of falling short, past the line at 25 percent where risk turns
        medium.
      </desc>
      <defs>
        <linearGradient id={`${id}-plate`} x2="1" y2="1">
          <stop stopColor="var(--forecast-ink)" stopOpacity="0.7" />
          <stop offset="0.4" stopColor="var(--forecast-steel)" />
          <stop offset="1" stopColor="var(--shade-3)" />
        </linearGradient>
        <linearGradient id={`${id}-side`} x1="0" y1="0" x2="0" y2="1">
          <stop stopColor="var(--forecast-steel)" />
          <stop offset="0.5" stopColor="var(--shade-3)" />
          <stop offset="1" stopColor="var(--ground)" />
        </linearGradient>
        <linearGradient id={`${id}-marker`} x2="0.3" y2="1">
          <stop stopColor="var(--paper)" />
          <stop offset="0.7" stopColor="var(--glow)" />
          <stop offset="1" stopColor="var(--ore)" />
        </linearGradient>
        <radialGradient id={`${id}-shadow`}>
          <stop stopColor="var(--ink)" stopOpacity="0.62" />
          <stop offset="1" stopColor="var(--ink)" stopOpacity="0" />
        </radialGradient>
      </defs>

      <ellipse className={f.shadow} cx="200" cy="520" rx="220" ry="46" fill={`url(#${id}-shadow)`} />
      <ellipse className={f.shadow} cx="440" cy="380" rx="170" ry="54" fill={`url(#${id}-shadow)`} />
      <ellipse className={f.shadow} cx={coin.cx + 10} cy={coin.cy + coin.depth + 20} rx="150" ry="42" fill={`url(#${id}-shadow)`} />

      {/* The future sits behind today's marker, so it is drawn first. */}
      <g data-future>
        <g className={f.part} data-on={band} onPointerEnter={() => setBand(true)} onPointerLeave={() => setBand(false)}>
          <path className={f.hit} d={full.front} />
          <path className={f.bandBack} data-band-back d={full.back} />
          <g data-guess>
            <path className={f.guess} d={path(MONTHS.map((t) => P(t, bandDepth.mid, guessAt(t))))} />
            {MONTHS.slice(1).map((t) => {
              const [x, y] = P(t, bandDepth.mid, guessAt(t));
              return <circle key={t} className={f.guessDot} cx={x} cy={y} r="3.2" />;
            })}
          </g>
          <path className={f.bandLid} data-band-lid d={full.lid} />
          <path className={f.bandFront} data-band-front d={full.front} />
          <path className={f.bandEdge} data-band-upper d={full.upper} />
          <path className={f.bandEdge} data-band-lower d={full.lower} />
          <g className={f.minMax}>
            <path className={f.leader} d={path([nextUpper, [nextUpper[0] + 14, nextUpper[1] - 18]])} />
            <text x={nextUpper[0] + 18} y={nextUpper[1] - 20}>max 2,25,810 t</text>
            <path className={f.leader} d={path([nextLower, [nextLower[0] + 14, nextLower[1] + 18]])} />
            <text x={nextLower[0] + 18} y={nextLower[1] + 28}>min 1,77,731 t</text>
          </g>
        </g>
        <text className={f.groupLabel} x={bandEndTop[0] + 56} y={bandEndTop[1] - 24}>WHAT COULD HAPPEN</text>
        <path className={f.leader} d={path([[bandEndTop[0] + 50, bandEndTop[1] - 28], [bandEndTop[0] + 8, bandEndTop[1] - 28], [bandEndTop[0] + 2, bandEndTop[1] - 6]])} />
        <circle className={f.leaderDot} cx={bandEndTop[0] + 1} cy={bandEndTop[1] - 3} r="2" />
      </g>

      <g data-marker>
        <path d={path([P(TODAY, 0, marker.height), P(TODAY, depth, marker.height), P(TODAY, depth, 0), P(TODAY, 0, 0)], true)} fill={`url(#${id}-marker)`} />
        <path d={path([P(TODAY, depth, marker.height), P(TODAY + marker.thickness, depth, marker.height), P(TODAY + marker.thickness, depth, 0), P(TODAY, depth, 0)], true)} fill="var(--ore)" />
        <path d={path([P(TODAY, 0, marker.height), P(TODAY + marker.thickness, 0, marker.height), P(TODAY + marker.thickness, depth, marker.height), P(TODAY, depth, marker.height)], true)} fill="var(--paper)" />
        <text className={f.groupLabel} x={markerTop[0] - 110} y={markerTop[1] - 40}>TODAY</text>
        <text className={f.subLabel} x={markerTop[0] - 110} y={markerTop[1] - 26}>ISSUE DATE</text>
        <path className={f.leader} d={path([[markerTop[0] - 110, markerTop[1] - 20], [markerTop[0], markerTop[1] - 20], [markerTop[0], markerTop[1] - 6]])} />
        <circle className={f.leaderDot} cx={markerTop[0]} cy={markerTop[1] - 4} r="2" />
      </g>

      <g data-terrace>
        {/* Nearer steps paint last: time runs away from the viewer. */}
        {actuals.map((z, i) => ({ z, i })).reverse().map(({ z, i }) => {
          const t0 = step * i, t1 = t0 + step;
          const low = Math.min(z, i === 0 ? z : (actuals[i - 1] ?? z)) - slab;
          return (
            <g key={i} data-step>
              <path d={path([P(t0, 0, z), P(t0, depth, z), P(t0, depth, low), P(t0, 0, low)], true)} fill="var(--shade-3)" />
              <path d={path([P(t0, depth, z), P(t1, depth, z), P(t1, depth, z - slab), P(t0, depth, z - slab)], true)} fill={`url(#${id}-side)`} />
              <path d={path([P(t0, 0, z), P(t1, 0, z), P(t1, depth, z), P(t0, depth, z)], true)} fill={`url(#${id}-plate)`} />
              <path className={f.edge} d={path([P(t0, depth, z), P(t1, depth, z), P(t1, 0, z)])} />
            </g>
          );
        })}
        <text className={f.groupLabel} x="10" y="330">WHAT REALLY HAPPENED</text>
        <path className={f.leader} d={path([[10, 338], [firstStep[0], 338], [firstStep[0], firstStep[1] - 6]])} />
        <circle className={f.leaderDot} cx={firstStep[0]} cy={firstStep[1] - 4} r="2" />
      </g>

      <g data-coin>
        <g className={f.part} data-on={gauge} onPointerEnter={() => setGauge(true)} onPointerLeave={() => setGauge(false)}>
          <ellipse className={f.hit} cx={coin.cx} cy={coin.cy + coin.depth / 2} rx={coin.rx + 10} ry={coin.ry + coin.depth} />
          <path
            d={`M${coin.cx - coin.rx} ${coin.cy}A${coin.rx} ${coin.ry} 0 0 0 ${coin.cx + coin.rx} ${coin.cy}V${coin.cy + coin.depth}A${coin.rx} ${coin.ry} 0 0 1 ${coin.cx - coin.rx} ${coin.cy + coin.depth}Z`}
            fill={`url(#${id}-side)`}
          />
          <ellipse cx={coin.cx} cy={coin.cy} rx={coin.rx} ry={coin.ry} fill={`url(#${id}-plate)`} />
          <ellipse className={f.edge} cx={coin.cx} cy={coin.cy} rx={coin.rx} ry={coin.ry} />
          <path className={f.ring} d={coinSector(0, 0.9999)} />
          <path className={f.risk} d={coinSector(0, coin.risk)} />
          <ellipse cx={coin.cx} cy={coin.cy} rx={coin.rx * 0.16} ry={coin.ry * 0.16} fill="var(--shade-3)" />
          <path className={f.tick} d={path(lineTick)} />
          <text className={f.lineLabel} x={(lineTick[1]?.[0] ?? 0) + 8} y={(lineTick[1]?.[1] ?? 0) + 4}>THE LINE</text>
        </g>
        <text className={f.groupLabel} x={coin.cx - 20} y={coin.cy - coin.ry - 44} textAnchor="middle">CHANCE OF SHORTFALL</text>
        <path className={f.leader} d={path([[coin.cx - 20, coin.cy - coin.ry - 40], [coin.cx - 20, coin.cy - coin.ry * coin.outer - 4]])} />
        <circle className={f.leaderDot} cx={coin.cx - 20} cy={coin.cy - coin.ry * coin.outer - 2} r="2" />
      </g>
    </svg>
  );
}
