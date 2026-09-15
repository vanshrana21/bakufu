import type { CSSProperties, ReactNode } from "react";
import s from "./briefing.module.css";

type Vars = CSSProperties & Record<`--${string}`, string | number>;

const STRIP = Array.from({ length: 20 }, (_, i) => <span key={i}>{i % 10}</span>);

/** A number whose digits roll into place on first paint. Pure CSS: the resting
 * transform is the true digit, so no JavaScript, print or reduced motion can
 * ever leave it showing anything else. The real value is read to assistive tech. */
export function RollingNumber({ value, delay = 0, testId }: { value: string; delay?: number; testId?: string }) {
  let digit = 0;
  return <span className={s.roll}>
    <span className="sr-only" data-testid={testId}>{value}</span>
    <span className={s.rollGlyphs} aria-hidden="true">
      {[...value].map((char, i) => /\d/.test(char)
        ? <span key={i} className={s.digit}>
          <span className={s.strip} style={{ "--d": Number(char), "--i": digit++, "--delay": `${delay}ms` } as Vars}>{STRIP}</span>
        </span>
        : <span key={i} className={s.glyph}>{char}</span>)}
    </span>
  </span>;
}

export function Dot({ tone, pulse = false }: { tone: "good" | "attention" | "synthetic" | "info"; pulse?: boolean }) {
  return <span className={s.dot} data-tone={tone} data-pulse={pulse || undefined} aria-hidden="true" />;
}

/** Twelve months of measured output as a line and a soft area. */
export function Sparkline({ values, label }: { values: readonly number[]; label: string }) {
  if (values.length < 2) return null;
  const width = 400, height = 110, pad = 8;
  const min = Math.min(...values), max = Math.max(...values);
  const span = max - min || 1;
  const points = values.map((value, i) => [
    (i / (values.length - 1)) * width,
    pad + (1 - (value - min) / span) * (height - pad * 2),
  ] as const);
  const line = points.map(([x, y], i) => `${i ? "L" : "M"}${x.toFixed(1)} ${y.toFixed(1)}`).join("");
  const area = `${line}L${width} ${height}L0 ${height}Z`;
  const [lastX, lastY] = points[points.length - 1]!;
  return <div className={s.spark} role="img" aria-label={label}>
    <svg viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none" aria-hidden="true">
      <defs>
        <linearGradient id="briefing-spark" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0" stopColor="var(--ore)" stopOpacity="0.32" />
          <stop offset="1" stopColor="var(--ore)" stopOpacity="0" />
        </linearGradient>
      </defs>
      <path className={s.sparkArea} d={area} fill="url(#briefing-spark)" />
      <path className={s.sparkLine} d={line} pathLength={1} fill="none" vectorEffect="non-scaling-stroke" />
    </svg>
    <span className={s.sparkPoint} style={{ left: `${(lastX / width) * 100}%`, top: `${(lastY / height) * 100}%` }} />
  </div>;
}

/** A half dial for the shortfall chance, with the page's disclosed display bands. */
export function Dial({ percent, tone }: { percent: number; tone: "good" | "attention" }) {
  const value = Math.max(0, Math.min(100, percent));
  const arc = "M20 100 A80 80 0 0 1 180 100";
  return <svg className={s.dial} viewBox="0 0 200 112" aria-hidden="true" style={{ "--v": value } as Vars}>
    <path d={arc} pathLength={100} className={s.dialTrack} />
    <path d={arc} pathLength={100} className={s.dialZone} data-zone="low" strokeDasharray="29.4 70.6" />
    <path d={arc} pathLength={100} className={s.dialZone} data-zone="review" strokeDasharray="0 30.3 29.4 40.3" />
    <path d={arc} pathLength={100} className={s.dialZone} data-zone="high" strokeDasharray="0 60.3 39.7" />
    <path d={arc} pathLength={100} className={s.dialValue} data-tone={tone} />
    <g className={s.dialNeedle}>
      <circle cx="20" cy="100" r="7" data-tone={tone} />
    </g>
  </svg>;
}

export function StatusChip({ tone, children }: { tone: "good" | "attention" | "info"; children: ReactNode }) {
  return <span className={s.chip} data-tone={tone}>{children}</span>;
}
