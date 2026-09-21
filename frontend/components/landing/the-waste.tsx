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
        <span>THE WASTE / ख</span>
      </header>
      <div className={w.body}>
        <div className={w.content}>
          <h2 id="waste-heading" className={w.title}>
            THE WASTE <span>IS NOT EMPTY.</span>
          </h2>
          <div className={w.copy}>
            <p className={w.lead}>Old mines left a lot of waste behind.</p>
            <p className={w.explanation}>That waste can still contain manganese.</p>
            <p className={w.conclusion}>We check the waste before digging new mines.</p>
            <span className={w.footnote}>
              A screening opportunity. Recovery requires sampling, assays and
              process feasibility.
            </span>
          </div>
        </div>
        <figure className={w.art}>
          <WasteCutaway />
          <span className={w.card}>
            RECLASSIFY
            <strong>THE DISCARDED.</strong>
          </span>
          <figcaption>Conceptual cutaway · Not an assay</figcaption>
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
