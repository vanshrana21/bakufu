import { ChapterLabel } from "./shared";
import s from "./story.module.css";
const sources = [
  ["01", "SENTINEL-2", "STAC imagery"],
  ["02", "TERRAIN / DEM", "Elevation & structure"],
  ["03", "IMD RAINFALL", "Temporal context"],
  ["04", "MOIL / BSE", "Production filings"],
];
const models = [
  ["PU-XGBOOST v6", "Prospectivity / positive-unlabeled"],
  ["PROPHET", "Company-wide production"],
  ["XGBOOST", "Shortfall classification"],
  ["AUTOENCODER", "Unlabelled spatial representations"],
];
export function TheEngine() {
  return (
    <section
      className={s.chapter + " " + s.engine}
      data-pin="engine"
      aria-labelledby="engine-heading"
    >
      <ChapterLabel number="03">
        THE ENGINE / FROM INPUT TO EVIDENCE
      </ChapterLabel>
      <div className={s.sectionIntro}>
        <h2 id="engine-heading" className={s.display}>
          NO MAGIC.
          <br />
          METHOD.
        </h2>
        <p>
          Different signals. Different jobs.
          <br />
          One inspectable chain of evidence.
        </p>
      </div>
      <div className={s.pipeline}>
        <div className={s.pipelineColumn}>
          {sources.map(([n, title, sub]) => (
            <div className={s.pipelineNode} data-node key={title}>
              <span>{n}</span>
              <div>
                <strong>{title}</strong>
                <p>{sub}</p>
              </div>
            </div>
          ))}
        </div>
        <svg
          className={s.pipelineLines}
          viewBox="0 0 180 300"
          preserveAspectRatio="none"
          aria-hidden="true"
        >
          <path
            data-draw
            d="M0 30H40V150H90M0 110H40M0 190H40V150M0 270H40V190M90 150h45V30h45M135 150v-40h45M135 150v40h45M135 190v80h45"
            fill="none"
            stroke="var(--glow)"
            strokeWidth="2"
          />
          <circle cx="90" cy="150" r="9" fill="var(--glow)" />
        </svg>
        <div className={s.featureLattice} data-node>
          <span>FEATURE LATTICES</span>
          <div aria-hidden="true">
            {Array.from({ length: 25 }, (_, i) => (
              <i key={i} />
            ))}
          </div>
          <p>
            Spatial + temporal
            <br />
            separate pipelines
          </p>
        </div>
        <div className={s.pipelineColumn}>
          {models.map(([title, sub]) => (
            <div className={s.modelNode} data-node key={title}>
              <strong>{title}</strong>
              <p>{sub}</p>
            </div>
          ))}
        </div>
      </div>
      <div className={s.engineEvidence}>
        <div>
          <span>REPORTED SPATIAL VALIDATION</span>
          <strong>
            LOBO AUC <b data-counter="0.9034">0.9034</b>
          </strong>
        </div>
        <p>
          Held-out geographic blocks. Positive-unlabeled learning.
          <br />
          Sausar gondite geology only. Not a nationwide guarantee.
        </p>
      </div>
      <p className={s.footnote}>
        Architecture diagram: imagery + DEM → spatial features; rainfall +
        production filings → temporal features. Arrows show orchestration, not a
        shared training table.
      </p>
    </section>
  );
}
