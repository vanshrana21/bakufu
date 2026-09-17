"use client";

import { useEffect, useRef } from "react";
import styles from "./sheet-frame.module.css";

/** The extent every sheet of the atlas is drawn at: the Sausar Belt `full_bbox`
 * the backend warms (lib/api/heatmap.ts WARM_VIEWPORTS.full_bbox), which is also
 * the model's validated scope. tests/unit/sheet-extent.test.ts keeps the two in
 * step, so the frame can never quietly claim a different area than the map. */
export const SHEET_EXTENT = { west: 79.0, east: 80.6, south: 21.3, north: 22.1 } as const;

/** Graticule stops: the four quarter lines and both neatlines. */
const STOPS = [0, 0.25, 0.5, 0.75, 1] as const;

/** 79.4 -> "79°24′E". Degrees and whole minutes, the way a sheet edge is labelled. */
export function formatDegrees(value: number, positive: string, negative: string): string {
  const hemisphere = value < 0 ? negative : positive;
  const absolute = Math.abs(value);
  let whole = Math.floor(absolute);
  let minutes = Math.round((absolute - whole) * 60);
  if (minutes === 60) {
    whole += 1;
    minutes = 0;
  }
  return `${whole}°${String(minutes).padStart(2, "0")}′${hemisphere}`;
}
export const formatLongitude = (value: number) => formatDegrees(value, "E", "W");
export const formatLatitude = (value: number) => formatDegrees(value, "N", "S");

const edge = (stop: number) => (stop === 0 ? "start" : stop === 1 ? "end" : "mid");

/** The sheet's margin: a longitude ruler under the scope band, a latitude ruler
 * down the left edge, and a copper cursor that reads the pointer back as sheet
 * coordinates.
 *
 * The rulers are decoration and are hidden from assistive technology; the band
 * text and the legend are real content. The cursor writes straight to the DOM
 * inside one animation frame per pointer move, so moving the mouse never renders
 * React and never touches layout-affecting properties.
 */
export function SheetFrame() {
  const longitudeRuler = useRef<HTMLDivElement>(null);
  const latitudeRuler = useRef<HTMLDivElement>(null);
  const longitudeMarker = useRef<HTMLSpanElement>(null);
  const latitudeMarker = useRef<HTMLSpanElement>(null);

  useEffect(() => {
    const across = longitudeRuler.current;
    const down = latitudeRuler.current;
    const acrossMark = longitudeMarker.current;
    const downMark = latitudeMarker.current;
    if (!across || !down || !acrossMark || !downMark) return;
    // Following the pointer only means something where there is a pointer to
    // follow; on touch there is no hover, so the rulers simply stay static.
    if (typeof window.matchMedia !== "function" || !window.matchMedia("(pointer: fine)").matches) return;
    const column = across.closest<HTMLElement>(".workspace-main");
    if (!column) return;
    const acrossLabel = acrossMark.querySelector("b");
    const downLabel = downMark.querySelector("b");

    let frame = 0;
    let x = 0;
    let y = 0;
    const draw = () => {
      frame = 0;
      const area = column.getBoundingClientRect();
      const inside = x >= area.left && x <= area.right && y >= area.top && y <= area.bottom;
      column.dataset.sheetCursor = inside ? "on" : "off";
      if (!inside) return;
      const horizontal = across.getBoundingClientRect();
      const vertical = down.getBoundingClientRect();
      if (horizontal.width === 0 || vertical.height === 0) return;
      const fx = Math.min(1, Math.max(0, (x - horizontal.left) / horizontal.width));
      const fy = Math.min(1, Math.max(0, (y - vertical.top) / vertical.height));
      acrossMark.style.transform = `translate3d(${(fx * horizontal.width).toFixed(1)}px, 0, 0)`;
      downMark.style.transform = `translate3d(0, ${(fy * vertical.height).toFixed(1)}px, 0)`;
      // Near the far edge the readout flips to the inside, so it is never clipped.
      acrossMark.dataset.flip = fx > 0.82 ? "true" : "false";
      downMark.dataset.flip = fy > 0.82 ? "true" : "false";
      if (acrossLabel) acrossLabel.textContent = formatLongitude(SHEET_EXTENT.west + fx * (SHEET_EXTENT.east - SHEET_EXTENT.west));
      if (downLabel) downLabel.textContent = formatLatitude(SHEET_EXTENT.north - fy * (SHEET_EXTENT.north - SHEET_EXTENT.south));
    };
    const move = (event: PointerEvent) => {
      x = event.clientX;
      y = event.clientY;
      if (!frame) frame = requestAnimationFrame(draw);
    };
    const leave = () => {
      column.dataset.sheetCursor = "off";
    };
    window.addEventListener("pointermove", move, { passive: true });
    document.documentElement.addEventListener("pointerleave", leave);
    return () => {
      window.removeEventListener("pointermove", move);
      document.documentElement.removeEventListener("pointerleave", leave);
      if (frame) cancelAnimationFrame(frame);
      delete column.dataset.sheetCursor;
    };
  }, []);

  const { west, east, south, north } = SHEET_EXTENT;
  return (
    <>
      <div ref={latitudeRuler} className={styles.latitude} aria-hidden="true">
        {STOPS.map((stop) => (
          <span key={stop} className={styles.latitudeLabel} data-edge={edge(stop)} style={{ top: `${stop * 100}%` }}>
            {formatLatitude(north - stop * (north - south))}
          </span>
        ))}
        <span ref={latitudeMarker} className={`${styles.marker} ${styles.latitudeMarker}`}>
          <b />
        </span>
      </div>
      <div className={styles.band}>
        <div className={styles.bandText}>
          <span>Sausar Belt · Gondite geology</span>
          <span className={styles.legend}>
            <span data-ink="observed">Observed</span>
            <span data-ink="model">Model estimate</span>
            <span data-ink="action">Action</span>
          </span>
          <span>September 2026 scenario</span>
        </div>
        <div ref={longitudeRuler} className={styles.longitude} aria-hidden="true">
          {STOPS.map((stop) => (
            <span key={stop} className={styles.longitudeLabel} data-edge={edge(stop)} style={{ left: `${stop * 100}%` }}>
              {formatLongitude(west + stop * (east - west))}
            </span>
          ))}
          <span ref={longitudeMarker} className={`${styles.marker} ${styles.longitudeMarker}`}>
            <b />
          </span>
        </div>
      </div>
    </>
  );
}
