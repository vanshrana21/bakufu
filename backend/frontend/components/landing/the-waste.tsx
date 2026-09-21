import localFont from "next/font/local";
import { WasteCutaway } from "./waste-cutaway";
import { TerrainAtmosphere } from "./terrain-atmosphere";
import s from "./story.module.css";
import w from "./waste.module.css";

const wasteSans = localFont({
  src: "./fonts/public-sans-latin-variable.woff2",
  weight: "400 700",
  display: "swap",
  variable: "--font-waste",
});

export function TheWaste() {
  return (
    <section
      id="waste"
      className={`${s.chapter} ${w.section} ${wasteSans.variable}`}
      aria-labelledby="waste-heading"
    >
      <TerrainAtmosphere variant="waste" />
      <header className={w.label}>
        <span>01 / FIELD NOTES</span>
        <span>THE BELT / 帯</span>
      </header>
      <div className={w.body}>
        <div className={w.content}>
          <h2 id="waste-heading" className={w.title}>
            TEN MINES. <span>ONE BELT.</span>
          </h2>
          <div className={w.copy}>
            <p className={w.lead}>MOIL works ten manganese mines in the Sausar Belt.</p>
            <p className={w.explanation}>The ground between them has never been screened cell by cell.</p>
            <p className={w.conclusion}>Satellite imagery already covers all of it.</p>
            <span className={w.footnote}>
              A screening opportunity, not a discovery. Sampling, assays and
              approvals still come first.
            </span>
          </div>
        </div>
        <figure className={w.art}>
          <WasteCutaway />
          <span className={w.card}>
            READ
            <strong>THE GROUND BETWEEN.</strong>
          </span>
          <figcaption>Conceptual cutaway · Not a measured section</figcaption>
        </figure>
      </div>
      <div className={w.facts}>
        <span>
          <strong>01</strong> BELT. A DELIBERATE SCOPE.
        </span>
        <span>
          <strong>10</strong> WORKSPACE MODULES.
        </span>
        <span>LESS ASSUMPTION. MORE EVIDENCE.</span>
      </div>
    </section>
  );
}
