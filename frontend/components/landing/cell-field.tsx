"use client";
import { useEffect, useRef } from "react";
import s from "./story.module.css";
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
          const edge =
            y < 4 + Math.sin(x / 4) * 3 || y > 25 + Math.cos(x / 5) * 4;
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
      for (const [x, y] of [
        [9, 14],
        [22, 18],
      ] as const) {
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
    <canvas
      ref={ref}
      className={s.cellCanvas}
      data-cell-field
      role="img"
      aria-label="Illustrative 32 by 32 prospectivity field with hatched exclusions, transparent out-of-scope cells, and two waste candidate diamonds"
    >
      Illustration: raw model scores are screened by masks. Out-of-scope cells
      have no prediction.
    </canvas>
  );
}
