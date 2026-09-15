import localFont from "next/font/local";
import { LoopVisual } from "./loop-visual";
import { TerrainAtmosphere } from "./terrain-atmosphere";
import s from "./story.module.css";
import l from "./loop.module.css";

const loopSans = localFont({
  src: "./fonts/public-sans-latin-variable.woff2",
  weight: "400 700",
  display: "swap",
  variable: "--font-loop",
});

export function TheLoop() {
  return (
    <section
      id="loop"
      className={`${s.chapter} ${l.section} ${loopSans.variable}`}
      aria-labelledby="loop-heading"
    >
      <TerrainAtmosphere variant="screening" />
      <span className={`${s.chapterIndex} ${l.index}`} aria-hidden="true">07</span>
      <header className={l.label}>
        <span>07 / FIELD NOTES</span>
        <span>STAGE 9 / HOW IT LEARNS / 巡</span>
      </header>
      <div className={l.intro}>
        <h2 id="loop-heading" className={l.title}>
          PEOPLE TEACH <span>THE MACHINE.</span>
        </h2>
        <p className={l.aside}>
          When the model gets it wrong, a person says so.
          <span>That correction trains the next version.</span>
        </p>
      </div>
      <div className={l.body}>
        <figure className={l.visual}>
          <div className={l.stage}>
            <LoopVisual />
            <span className={l.sticker}>
              STAGE 9
              <strong>HUMAN KNOWLEDGE, VERSIONED.</strong>
            </span>
          </div>
          <figcaption>
            Workflow illustration · Feedback alone does not prove the model got better. The held-out test still decides.
          </figcaption>
        </figure>
        <div className={l.text}>
          <div className={l.stanza}>
            <p>The model points at a place.</p>
            <p>A geologist walks it, or checks the records.</p>
            <p>If the model was wrong, we write down why.</p>
            <p>The next version learns from it — and still has to pass the test.</p>
          </div>
          <div className={l.moment}>
            <span>MODEL VERSION</span>
            <strong>
              v6 <span className={l.arrow}>→</span> <span className={l.next}>v7</span>
            </strong>
            <p className={l.gloss}>
              The new version must beat the old one on places it has never seen. Until then, it waits.
            </p>
          </div>
        </div>
      </div>
    </section>
  );
}
