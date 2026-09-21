"use client";

import { useEffect, useId, useRef, useState, type Dispatch, type PointerEvent, type SetStateAction } from "react";
import { gsap } from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import e from "./engine.module.css";

type Pt = readonly [number, number];
type Glyph = "photo" | "terrain" | "rain" | "ledger";

const INPUTS: readonly { name: string; sub: string; glyph: Glyph }[] = [
  { name: "SENTINEL-2", sub: "Photos from space", glyph: "photo" },
  { name: "TERRAIN / DEM", sub: "Shape of the land", glyph: "terrain" },
  { name: "IMD RAINFALL", sub: "Rain over the years", glyph: "rain" },
  { name: "MOIL / BSE", sub: "Old mining records", glyph: "ledger" },
];
/* Questions are broken where they fit a slab face; the words are unchanged. */
const MODELS: readonly { name: string; question: readonly string[] }[] = [
  { name: "PU-XGBOOST v6", question: ["Is metal hiding here?"] },
  { name: "PROPHET", question: ["How much will we dig", "next month?"] },
  { name: "XGBOOST", question: ["Will we dig less", "than planned?"] },
  { name: "AUTOENCODER", question: ["Does something", "look strange?"] },
];

/* The bench, in viewBox units. Beams bend only along the floor and straight up,
 * and the risers are placed so no two beams ever cross. */
const BENCH = {
  view: [1070, 660],
  input: { x: 262, y: [100, 228, 356, 484], size: 84, depth: 10, riser: [null, 354, 368, 382] },
  lattice: { top: [600, 214] as Pt, size: 210, depth: 16, cells: 4, inset: 4.5, seam: 2.5 },
  /** Tiles lit at rest, as [column, cell]: a few answers already forming. */
  lit: ["0-1", "1-3", "2-0", "3-2"],
  node: { u: 157.5, v: 105 },
  model: { x: 890, y: [120, 244, 368, 492], width: 160, height: 92, depth: 12, riser: [836, 860, null, 836] },
} as const;

/* Scroll-in: the three parts drift together from opposite sides while the beams draw. */
const MOTION = {
  drift: { x: 22, y: 10, lattice: 26, duration: 0.55 },
  draw: { duration: 0.3, stagger: 0.09, inputsAt: 0.2, modelsAt: 0.62 },
} as const;
/** Beams use a long path length: GSAP rounds dash offsets to whole units. */
const BEAM_LENGTH = 1000;

/* One floor projection for the whole bench, with the 0.4 slope of the plates in
 * chapters 01 and 02: u runs right-down, v runs left-down, z runs straight up. */
const SLOPE = 0.4;
const at = ([x, y]: Pt, u: number, v: number, z = 0): Pt => [x + u - v, y + SLOPE * (u + v) - z];
/** The point at x on the floor line through p. */
const along = ([x0, y0]: Pt, x: number): Pt => [x, y0 + SLOPE * (x - x0)];
const num = (n: number) => String(Math.round(n * 10) / 10);
const path = (points: readonly Pt[], close = false) =>
  `M${points.map(([x, y]) => `${num(x)} ${num(y)}`).join("L")}${close ? "Z" : ""}`;

/** Top face corners of a flat plate from its back corner: back, right, front, left. */
function plate(back: Pt, size: number) {
  return [back, at(back, size, 0), at(back, size, size), at(back, 0, size)] as const;
}

function InputGlyph({ kind, c }: { kind: Glyph; c: Pt }) {
  const k = 1.2; // glyph scale on the input slab
  const face = (u: number, v: number, z = 0) => at(c, u * k, v * k, z * k);
  const ellipse = (r: number, z: number) => (
    <ellipse cx={c[0]} cy={c[1] - z * k} rx={r * k * Math.SQRT2} ry={r * k * Math.SQRT2 * SLOPE} />
  );
  if (kind === "photo") {
    return (
      <g className={e.glyph}>
        <path className={e.glyphFill} d={path([face(-14, -14), face(14, -14), face(14, 14), face(-14, 14)], true)} />
        <path d={path([face(-22, -22), face(22, -22), face(22, 22), face(-22, 22)], true)} />
        <circle cx={face(8, -8)[0]} cy={face(8, -8)[1]} r="2.6" className={e.glyphDot} />
      </g>
    );
  }
  if (kind === "terrain") {
    return <g className={e.glyph}>{ellipse(24, 0)}{ellipse(15, 4)}{ellipse(7, 8)}</g>;
  }
  if (kind === "rain") {
    const drops: readonly [number, number][] = [[-14, 6], [0, -8], [14, 8]];
    return (
      <g className={e.glyph}>
        {drops.map(([u, v]) => {
          const [x, y] = face(u, v);
          return (
            <g key={`${u}${v}`}>
              <path d={path([[x, y - 26], [x, y - 9]])} />
              <ellipse cx={x} cy={y} rx="6" ry="2.4" />
            </g>
          );
        })}
      </g>
    );
  }
  return (
    <g className={e.glyph}>
      {[-15, -5, 5, 15].map((v) => <path key={v} d={path([face(-22, v), face(22, v)])} />)}
      <path className={e.glyphMargin} d={path([face(-12, -22), face(-12, 22)])} />
    </g>
  );
}

/** Pointer handlers that light one part: hover for mouse and pen, tap to toggle on touch. */
function lights(set: Dispatch<SetStateAction<number | null>>, index: number) {
  return {
    onPointerEnter: (event: PointerEvent) => { if (event.pointerType !== "touch") set(index); },
    onPointerLeave: (event: PointerEvent) => { if (event.pointerType !== "touch") set(null); },
    onPointerUp: (event: PointerEvent) => {
      if (event.pointerType === "touch") set((current) => (current === index ? null : index));
    },
  };
}

/** Conceptual orchestration diagram, not a training graph or live pipeline status. */
export function EngineVisual() {
  const id = useId().replace(/:/g, "");
  const ref = useRef<SVGSVGElement>(null);
  const [input, setInput] = useState<number | null>(null);
  const [model, setModel] = useState<number | null>(null);

  useEffect(() => {
    const svg = ref.current;
    if (!svg) return;
    gsap.registerPlugin(ScrollTrigger);
    const media = gsap.matchMedia();
    media.add("(prefers-reduced-motion: no-preference)", () => {
      const pick = gsap.utils.selector(svg);
      const { drift, draw } = MOTION;
      const beamsIn = pick("[data-beam-in]"), beamsOut = pick("[data-beam-out]");
      const endsIn = pick("[data-beam-end-in]"), endsOut = pick("[data-beam-end-out]");
      // Every beam starts hidden, not only the first of each staggered group.
      gsap.set([...beamsIn, ...beamsOut], { strokeDasharray: BEAM_LENGTH, strokeDashoffset: BEAM_LENGTH });
      gsap.set([...endsIn, ...endsOut], { opacity: 0 });
      const drawIn = { strokeDashoffset: 0, ease: "none", duration: draw.duration, stagger: draw.stagger };
      const showEnd = { opacity: 1, duration: 0.05, stagger: draw.stagger };
      gsap.timeline({
        defaults: { ease: "power2.out" },
        scrollTrigger: {
          id: "avnesh-engine", trigger: svg, start: "top 88%", end: "center 70%",
          scrub: 0.7, invalidateOnRefresh: true,
        },
      })
        .fromTo(pick("[data-engine-inputs]"), { x: -drift.x, y: drift.y }, { x: 0, y: 0, duration: drift.duration }, 0)
        .fromTo(pick("[data-engine-lattice]"), { y: drift.lattice }, { y: 0, duration: drift.duration }, 0)
        .fromTo(pick("[data-engine-models]"), { x: drift.x, y: -drift.y }, { x: 0, y: 0, duration: drift.duration }, 0)
        // Explicit start values survive a refresh, which re-records plain .to() tweens.
        .fromTo(beamsIn, { strokeDashoffset: BEAM_LENGTH }, drawIn, draw.inputsAt)
        .fromTo(endsIn, { opacity: 0 }, showEnd, draw.inputsAt + draw.duration - 0.05)
        .fromTo(beamsOut, { strokeDashoffset: BEAM_LENGTH }, drawIn, draw.modelsAt)
        .fromTo(endsOut, { opacity: 0 }, showEnd, draw.modelsAt + draw.duration - 0.05);
    });
    return () => media.revert();
  }, []);

  const { input: In, lattice: Lt, model: Md } = BENCH;
  const cell = Lt.size / Lt.cells;
  const [lTop, lRight, lFront, lLeft] = plate(Lt.top, Lt.size);
  const lDrop = (p: Pt): Pt => [p[0], p[1] + Lt.depth];
  const node = at(Lt.top, BENCH.node.u, BENCH.node.v);

  // Each input beam enters the middle of its own lattice column.
  const columnEntry = (k: number) => at(Lt.top, 0, (k + 0.5) * cell);
  const inputBeam = (i: number) => {
    const start = at([In.x, In.y[i] ?? 0], In.size, 0);
    const entry = columnEntry(i);
    const riser = In.riser[i];
    const points = riser == null ? [start, entry] : [start, along(start, riser), along(entry, riser), entry];
    return { start, entry, d: path(points) };
  };
  const modelEntry = (j: number): Pt => [Md.x, (Md.y[j] ?? 0) + Md.height / 2];
  const modelBeam = (j: number) => {
    const entry = modelEntry(j);
    const riser = Md.riser[j];
    const points = riser == null ? [node, entry] : [node, along(node, riser), along(entry, riser), entry];
    return { entry, d: path(points) };
  };

  return (
    <svg ref={ref} className={e.bench} viewBox={`0 0 ${BENCH.view.join(" ")}`} role="img" aria-labelledby={`${id}-title ${id}-desc`}>
      <title id={`${id}-title`}>Four inputs run into feature lattices, and four models each answer one question</title>
      <desc id={`${id}-desc`}>
        Inputs: SENTINEL-2, photos from space. TERRAIN / DEM, shape of the land. IMD RAINFALL, rain over the
        years. MOIL / BSE, old mining records. Each runs as a beam into the feature lattices. Four beams leave
        for four models: PU-XGBOOST v6, is metal hiding here? PROPHET, how much will we dig next month? XGBOOST,
        will we dig less than planned? AUTOENCODER, does something look strange? How the parts connect:
        orchestration, not a shared training table.
      </desc>
      <defs>
        <linearGradient id={`${id}-plate`} x2="1" y2="1">
          <stop stopColor="var(--engine-ink)" stopOpacity="0.7" />
          <stop offset="0.4" stopColor="var(--engine-steel)" />
          <stop offset="1" stopColor="var(--shade-3)" />
        </linearGradient>
        <linearGradient id={`${id}-face`} x2="1" y2="0.6">
          <stop stopColor="var(--engine-steel)" stopOpacity="0.9" />
          <stop offset="0.45" stopColor="var(--shade-3)" />
          <stop offset="1" stopColor="var(--ground)" />
        </linearGradient>
        <linearGradient id={`${id}-core`} x2="0.7" y2="1">
          <stop stopColor="var(--paper)" />
          <stop offset="0.5" stopColor="var(--glow)" />
          <stop offset="1" stopColor="var(--ore)" />
        </linearGradient>
        <radialGradient id={`${id}-shadow`}>
          <stop stopColor="var(--ink)" stopOpacity="0.62" />
          <stop offset="1" stopColor="var(--ink)" stopOpacity="0" />
        </radialGradient>
      </defs>

      <g data-engine-inputs>
        <ellipse cx={In.x + 4} cy={(In.y[3] ?? 0) + In.size * 0.8 + 40} rx="128" ry="30" className={e.shadow} fill={`url(#${id}-shadow)`} />
        <text x="20" y="56" className={e.groupLabel}>INPUTS</text>
        <path className={e.leader} d={path([[82, 52], [In.x, 52], [In.x, (In.y[0] ?? 0) - 6]])} />
        <circle className={e.leaderDot} cx={In.x} cy={(In.y[0] ?? 0) - 4} r="2" />
        {INPUTS.map((item, i) => {
          const [back, right, front, left] = plate([In.x, In.y[i] ?? 0], In.size);
          const drop = (p: Pt): Pt => [p[0], p[1] + In.depth];
          const on = input === i;
          return (
            <g key={item.name} className={e.part} data-on={on} {...lights(setInput, i)}>
              <rect className={e.hit} x="16" y={back[1] - 10} width={right[0] - 8} height={front[1] - back[1] + In.depth + 20} />
              <path d={path([left, front, drop(front), drop(left)], true)} fill="var(--shade-3)" />
              <path d={path([front, right, drop(right), drop(front)], true)} fill="var(--shade-2)" />
              <path d={path([back, right, front, left], true)} fill={`url(#${id}-plate)`} />
              <path className={e.edge} d={path([left, front, right])} />
              <InputGlyph kind={item.glyph} c={at(back, In.size / 2, In.size / 2)} />
              <path className={e.leader} d={path([[left[0] - 24, left[1]], [left[0] - 4, left[1]]])} />
              <text className={e.inputName} x={left[0] - 30} y={left[1] - 4} textAnchor="end">{item.name}</text>
              <text className={e.inputSub} x={left[0] - 30} y={left[1] + 12} textAnchor="end">{item.sub}</text>
            </g>
          );
        })}
      </g>

      <g data-engine-lattice>
        <ellipse cx={lFront[0]} cy={lFront[1] + 30} rx="300" ry="80" className={e.shadow} fill={`url(#${id}-shadow)`} />
        <text x={lTop[0]} y={lTop[1] - 50} textAnchor="middle" className={e.groupLabel}>FEATURE LATTICES</text>
        <path className={e.leader} d={path([[lTop[0], lTop[1] - 42], [lTop[0], lTop[1] - 8]])} />
        <circle className={e.leaderDot} cx={lTop[0]} cy={lTop[1] - 6} r="2" />
        <path d={path([lLeft, lFront, lDrop(lFront), lDrop(lLeft)], true)} fill="var(--shade-3)" />
        <path d={path([lFront, lRight, lDrop(lRight), lDrop(lFront)], true)} fill="var(--shade-2)" />
        <path d={path([lTop, lRight, lFront, lLeft], true)} fill={`url(#${id}-plate)`} fillOpacity="0.55" />
        <path className={e.edge} d={path([lLeft, lFront, lRight])} />
        {Array.from({ length: Lt.cells }, (_, k) => Array.from({ length: Lt.cells }, (_, j) => {
          // A slightly wider groove splits the spatial columns from the temporal ones.
          const near = k * cell + Lt.inset + (k === 2 ? Lt.seam : 0);
          const far = (k + 1) * cell - Lt.inset - (k === 1 ? Lt.seam : 0);
          const u0 = j * cell + Lt.inset, u1 = (j + 1) * cell - Lt.inset;
          const tile = [at(Lt.top, u0, near), at(Lt.top, u1, near), at(Lt.top, u1, far), at(Lt.top, u0, far)];
          const column = input === k;
          const resting = (BENCH.lit as readonly string[]).includes(`${k}-${j}`);
          return (
            <path
              key={`${k}-${j}`}
              className={e.tile}
              data-on={column}
              d={path(tile, true)}
              fill={column ? "var(--glow)" : resting ? `url(#${id}-core)` : "var(--engine-steel)"}
              fillOpacity={column ? 0.95 : resting ? 0.9 : 0.3}
            />
          );
        }))}
        <circle cx={node[0]} cy={node[1]} r="14" fill="var(--glow)" fillOpacity="0.2" />
        <circle cx={node[0]} cy={node[1]} r="4.5" fill="var(--glow)" />
      </g>

      <g className={e.beams}>
        {INPUTS.map((item, i) => {
          const beam = inputBeam(i);
          const on = input === i;
          return (
            <g key={item.name}>
              <path className={e.beam} data-on={on} data-beam-in pathLength={BEAM_LENGTH} d={beam.d} />
              <circle className={e.beamEnd} data-on={on} cx={beam.start[0]} cy={beam.start[1]} r="2.6" />
              <circle className={e.beamEnd} data-on={on} data-beam-end-in cx={beam.entry[0]} cy={beam.entry[1]} r="2.6" />
            </g>
          );
        })}
        {MODELS.map((item, j) => {
          const beam = modelBeam(j);
          const on = model === j;
          return (
            <g key={item.name}>
              <path className={e.beam} data-on={on} data-beam-out pathLength={BEAM_LENGTH} d={beam.d} />
              <circle className={e.beamEnd} data-on={on} data-beam-end-out cx={beam.entry[0]} cy={beam.entry[1]} r="2.6" />
            </g>
          );
        })}
      </g>

      <g data-engine-models>
        <text x={Md.x + Md.width + Md.depth} y="56" textAnchor="end" className={e.groupLabel}>FOUR MODELS, FOUR QUESTIONS</text>
        <path className={e.leader} d={path([[Md.x, 64], [Md.x, (Md.y[0] ?? 0) - 10]])} />
        <circle className={e.leaderDot} cx={Md.x} cy={(Md.y[0] ?? 0) - 8} r="2" />
        {MODELS.map((item, j) => {
          const corner: Pt = [Md.x, Md.y[j] ?? 0];
          const right = at(corner, Md.width, 0);
          const back = (p: Pt) => at(p, 0, -Md.depth);
          const low = (p: Pt): Pt => [p[0], p[1] + Md.height];
          const base = at(low(corner), Md.width / 2, 0);
          const on = model === j;
          return (
            <g key={item.name} className={e.part} data-on={on} {...lights(setModel, j)}>
              <ellipse cx={base[0] + 8} cy={base[1] + 12} rx="96" ry="13" className={e.shadow} fill={`url(#${id}-shadow)`}
                transform={`rotate(${num((Math.atan(SLOPE) * 180) / Math.PI)} ${num(base[0] + 8)} ${num(base[1] + 12)})`} />
              <path className={e.hit} d={path([corner, right, low(right), low(corner)], true)} />
              <path d={path([corner, right, back(right), back(corner)], true)} fill={`url(#${id}-plate)`} />
              <path d={path([right, back(right), low(back(right)), low(right)], true)} fill="var(--shade-2)" />
              <path className={e.face} d={path([corner, right, low(right), low(corner)], true)} fill={`url(#${id}-face)`} />
              <g transform={`matrix(1 ${SLOPE} 0 1 ${corner[0]} ${corner[1]})`}>
                <text className={e.modelName} x="14" y="27">{item.name}</text>
                {item.question.map((line, n) => (
                  <text key={line} className={e.modelQuestion} x="14" y={50 + n * 15}>{line}</text>
                ))}
              </g>
            </g>
          );
        })}
      </g>
    </svg>
  );
}
