"use client";
import Link from "next/link";
import { Fragment, useEffect, useRef } from "react";
import { gsap } from "gsap";
import f from "./finale.module.css";

/* Lusion's end-title hover, measured on lusion.co/about. Three random letters
 * roll up one line onto an identical copy and snap back unseen; underlines
 * draw in one after another and break around descenders. */
const ROLL = { letters: 3, duration: 0.9, stagger: 0.1, ease: "expo.out" } as const;
const STROKES = {
  duration: 0.6,
  ease: "power3.inOut",
  /** Start time of each underline, in order: row one, then row two left to right. */
  offsets: [0, 0.12, 0.48],
  /** Offset below the baseline, thickness, and clearance kept around any ink
   * that reaches down into the stroke (a descender), in em. */
  below: 0.14,
  thickness: 0.07,
  clearance: 0.09,
} as const;

type Run = { left: number; top: number; width: number; height: number };

/** Horizontal extent of a glyph's ink inside a band below the baseline, in px
 * from its pen position, or null when the glyph does not reach the band. */
function inkInBand(ctx: CanvasRenderingContext2D, font: string, letter: string, size: number, from: number, to: number) {
  const pad = Math.ceil(size * 0.5);
  const width = Math.ceil(size * 2);
  const baseline = Math.ceil(size * 1.2);
  ctx.canvas.width = width; // resizing clears the canvas and its font
  ctx.canvas.height = baseline + Math.ceil(size * 0.6);
  ctx.font = font;
  ctx.fillText(letter, pad, baseline);
  const top = Math.floor(baseline + from);
  const rows = Math.max(1, Math.ceil(to - from));
  const { data } = ctx.getImageData(0, top, width, rows);
  let min = Infinity;
  let max = -Infinity;
  for (let y = 0; y < rows; y++) {
    for (let x = 0; x < width; x++) {
      if ((data[(y * width + x) * 4 + 3] ?? 0) > 48) {
        min = Math.min(min, x);
        max = Math.max(max, x + 1);
      }
    }
  }
  return min === Infinity ? null : ([min - pad, max - pad] as const);
}

export function RollLink({ href, lines, label, className }: {
  href: string; lines: readonly string[]; label: string; className?: string;
}) {
  const ref = useRef<HTMLAnchorElement>(null);
  const text = lines.join("\n");

  useEffect(() => {
    const link = ref.current;
    const layer = link?.querySelector<HTMLElement>("[data-strokes]");
    const ctx = document.createElement("canvas").getContext("2d", { willReadFrequently: true });
    if (!link || !layer || !ctx) return;
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)");
    const rows = Array.from(link.querySelectorAll<HTMLElement>("[data-row]"));
    const letters = Array.from(link.querySelectorAll<HTMLElement>("[data-roll]"));
    const rolling = new Set<HTMLElement>();
    let strokes: gsap.core.Timeline | null = null;
    let active = false;

    // Underline runs span letter ink, row by row, and stop short of any
    // descender that reaches down into the stroke.
    const measure = () => {
      const base = link.getBoundingClientRect();
      const runs: Run[] = [];
      for (const row of rows) {
        const cells = Array.from(row.querySelectorAll<HTMLElement>("[data-roll]"));
        const first = cells[0];
        if (!first) continue;
        const style = getComputedStyle(row);
        const size = parseFloat(style.fontSize);
        if (!(size > 0)) continue;
        const font = `${style.fontStyle} ${style.fontWeight} ${style.fontSize} ${style.fontFamily}`;
        ctx.font = font;
        const metrics = ctx.measureText("H");
        const ascent = metrics.fontBoundingBoxAscent;
        const lineHeight = parseFloat(getComputedStyle(first).lineHeight);
        const shift = (Number(gsap.getProperty(first, "yPercent")) / 100) * first.offsetHeight;
        const baseline = first.getBoundingClientRect().top - shift - base.top + (lineHeight - ascent - metrics.fontBoundingBoxDescent) / 2 + ascent;
        const top = baseline + STROKES.below * size;
        const height = STROKES.thickness * size;
        const clearance = STROKES.clearance * size;
        let start: number | null = null;
        let end = 0;
        const close = (at: number) => {
          if (start !== null && at > start) runs.push({ left: start, top, width: at - start, height });
          start = null;
        };
        for (const cell of cells) {
          const letter = cell.dataset.letter ?? "";
          const x = cell.getBoundingClientRect().left - base.left;
          ctx.font = font;
          const glyph = ctx.measureText(letter);
          const ink = inkInBand(ctx, font, letter, size, STROKES.below * size, (STROKES.below + STROKES.thickness) * size);
          if (ink) {
            close(x + ink[0] - clearance);
            start = x + ink[1] + clearance;
          } else {
            start ??= x - glyph.actualBoundingBoxLeft;
          }
          end = x + glyph.actualBoundingBoxRight;
        }
        close(end);
      }
      return runs;
    };

    const layout = () => {
      // Resize observers can still fire while the page is being torn down.
      if (!link.isConnected) return;
      strokes?.kill();
      const lines = measure().map((run) => {
        const line = document.createElement("i");
        Object.assign(line.style, { left: `${run.left}px`, top: `${run.top}px`, width: `${run.width}px`, height: `${run.height}px` });
        return line;
      });
      layer.replaceChildren(...lines);
      const timeline = gsap.timeline({ paused: true });
      lines.forEach((line, i) => {
        timeline.fromTo(line, { scaleX: 0 }, { scaleX: 1, duration: STROKES.duration, ease: STROKES.ease }, STROKES.offsets[i] ?? i * 0.24);
      });
      timeline.progress(active ? 1 : 0);
      strokes = timeline;
    };

    const roll = () => {
      if (reduce.matches) return;
      const idle = letters.filter((el) => !rolling.has(el));
      for (let i = 0; i < ROLL.letters; i++) {
        const [el] = idle.splice(Math.floor(Math.random() * idle.length), 1);
        if (!el) return;
        rolling.add(el);
        gsap.fromTo(el, { yPercent: 0 }, {
          yPercent: -100,
          duration: ROLL.duration,
          ease: ROLL.ease,
          delay: i * ROLL.stagger,
          onComplete: () => {
            gsap.set(el, { yPercent: 0 });
            rolling.delete(el);
          },
        });
      }
    };

    const enter = () => {
      if (active) return;
      active = true;
      roll();
      if (reduce.matches) strokes?.progress(1);
      else strokes?.play();
    };
    const leave = () => {
      if (!active) return;
      active = false;
      roll();
      if (reduce.matches) strokes?.progress(0);
      else strokes?.reverse();
    };
    const hover = (event: PointerEvent) => {
      if (event.pointerType === "touch") return;
      if (event.type === "pointerenter") enter();
      else leave();
    };

    layout();
    let alive = true;
    void document.fonts.ready.then(() => alive && layout());
    const resize = new ResizeObserver(() => layout());
    resize.observe(link);
    link.addEventListener("pointerenter", hover);
    link.addEventListener("pointerleave", hover);
    link.addEventListener("focus", enter);
    link.addEventListener("blur", leave);
    link.addEventListener("click", roll);
    return () => {
      alive = false;
      resize.disconnect();
      link.removeEventListener("pointerenter", hover);
      link.removeEventListener("pointerleave", hover);
      link.removeEventListener("focus", enter);
      link.removeEventListener("blur", leave);
      link.removeEventListener("click", roll);
      strokes?.kill();
      gsap.killTweensOf(letters);
      gsap.set(letters, { clearProps: "transform" });
      layer.replaceChildren();
    };
  }, [text]);

  return (
    <Link ref={ref} href={href} className={className} aria-label={label}>
      {lines.map((line, l) => (
        <span key={l} className={f.row} data-row aria-hidden="true">
          {line.split(" ").map((word, w) => (
            <Fragment key={w}>
              {w > 0 ? " " : null}
              <span className={f.word}>
                {Array.from(word).map((letter, c) => (
                  <span key={c} className={f.roll} data-roll data-letter={letter}>
                    <span>{letter}</span>
                    <span>{letter}</span>
                  </span>
                ))}
              </span>
            </Fragment>
          ))}
        </span>
      ))}
      <span className={f.strokes} data-strokes aria-hidden="true" />
    </Link>
  );
}
