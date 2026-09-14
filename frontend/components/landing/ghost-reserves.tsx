import localFont from "next/font/local";
import { ScreeningVisual } from "./screening-visual";
import { TerrainAtmosphere } from "./terrain-atmosphere";
import s from "./screening.module.css";

const screenSans = localFont({ src: "./fonts/public-sans-latin-variable.woff2", weight: "400 700", display: "swap", variable: "--font-screen" });
export function GhostReserves() {
  return (
    <section
      id="ghost"
      className={`${s.section} ${screenSans.variable}`}
      aria-labelledby="ghost-heading"
    >
      <TerrainAtmosphere variant="screening" />
      <header className={s.label}><span>02 / FIELD NOTES</span><span>GHOST RESERVES / SCREENING</span></header>
      <div className={s.body}>
        <div className={s.content}>
          <h2 id="ghost-heading" className={s.title}>WHAT WAS<span>LEFT BEHIND.</span></h2>
          <div className={s.copy}>
            <p className={s.lead}>Old waste can still have value.</p>
            <div className={s.steps}>
              <p>We find possible places.</p>
              <p>Then we remove the unsafe ones.</p>
              <p>Only the good ones stay.</p>
            </div>
          </div>
          <p className={s.caveat}>Geological and occurrence-buffer masks screen candidates. Retained sites still require environmental checks, assays and approvals.</p>
        </div>
        <figure className={s.visual}><ScreeningVisual /><figcaption>Conceptual screening sequence · Illustrative candidates</figcaption></figure>
      </div>
      <div className={s.evidence}>
        <div>
          <span>MODEL OUTPUT / RAW</span>
          <strong data-counter="0.84">0.84</strong>
        </div>
        <span className={s.arrow} aria-hidden="true">
          →
        </span>
        <div className={s.excluded}>
          <span>AFTER EXCLUSION / SCREENED</span>
          <strong data-counter="0.00">0.00</strong>
          <span className={s.exclusionLine} data-hatch aria-hidden="true" />
        </div>
        <aside>
          <b>SIGNAL ≠ PERMISSION.</b>
          <p>
            Illustrative excluded site.
            <br />
            Raw score preserved.
            <br />
            Mask reason recorded.
          </p>
        </aside>
      </div>
      <footer className={s.footer}><span>Screening indices, not ore tonnage.</span><span>Not a claim of measured ore.</span></footer>
    </section>
  );
}
