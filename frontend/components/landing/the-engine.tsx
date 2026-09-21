import localFont from "next/font/local";
import { EngineVisual } from "./engine-visual";
import { TerrainAtmosphere } from "./terrain-atmosphere";
import s from "./story.module.css";
import e from "./engine.module.css";

const engineSans = localFont({
  src: "./fonts/public-sans-latin-variable.woff2",
  weight: "400 700",
  display: "swap",
  variable: "--font-engine",
});

export function TheEngine() {
  return (
    <section
      id="engine"
      className={`${s.chapter} ${e.section} ${engineSans.variable}`}
      aria-labelledby="engine-heading"
    >
      <TerrainAtmosphere variant="waste" />
      <span className={`${s.chapterIndex} ${e.index}`} aria-hidden="true">03</span>
      <header className={e.label}>
        <span>03 / FIELD NOTES</span>
        <span>HOW IT WORKS / यन्त्र</span>
      </header>
      <div className={e.intro}>
        <h2 id="engine-heading" className={e.title}>
          WE SHOW <span>OUR WORK.</span>
        </h2>
        <p className={e.aside}>
          Four things go in. One answer comes out.
          <span>Nothing is hidden in between.</span>
        </p>
      </div>
      <div className={e.body}>
        <div className={e.text}>
          <div className={e.stanza}>
            <p>We look at photos from space.</p>
            <p>We look at the shape of the land.</p>
            <p>We look at rain and old mine records.</p>
            <p>Then we tell you what we found — and why.</p>
          </div>
          <div className={e.moment}>
            <span>OUR TEST SCORE</span>
            <strong data-counter="0.9034">0.9034</strong>
            <p className={e.gloss}>
              Out of 1.0 — tested on places it had never seen before. Sausar
              gondite geology only.
            </p>
          </div>
        </div>
        <figure className={e.visual}>
          <div className={e.stage}>
            <EngineVisual />
            <span className={e.sticker}>
              NO BLACK BOX
              <strong>EVERY STEP SHOWN.</strong>
            </span>
          </div>
          <figcaption>How the parts connect · Orchestration, not a shared training table.</figcaption>
        </figure>
      </div>
    </section>
  );
}
