import { ChapterLabel } from "./shared";
import { CellField } from "./cell-field";
import s from "./story.module.css";
export function TheMap() {
  return (
    <section
      className={s.chapter + " " + s.paper + " " + s.mapChapter}
      data-pin="map"
      aria-labelledby="map-heading"
    >
      <ChapterLabel number="04">
        MVP 01 / THE PROSPECTIVITY EXPLORER
      </ChapterLabel>
      <div className={s.sectionIntro}>
        <h2 id="map-heading" className={s.display}>
          SCREEN
          <br />
          THE BELT.
        </h2>
        <p>
          Not every bright pixel
          <br />
          deserves a green light.
        </p>
      </div>
      <div className={s.mapLayout}>
        <figure className={s.cellFigure}>
          <CellField />
          <figcaption>
            32 × 32 ILLUSTRATIVE CELLS / NOT A GEOGRAPHIC MAP
          </figcaption>
          <div className={s.cellLegend}>
            <span>
              <i />
              Score ramp
            </span>
            <span>
              <i className={s.hatchedKey} />
              Excluded
            </span>
            <span>
              <i className={s.nullKey} />
              No prediction
            </span>
            <span>◇ Waste candidate</span>
          </div>
        </figure>
        <aside className={s.mapInspector}>
          <span className={s.mono}>SELECTED EXAMPLE / GR–01</span>
          <h3>
            A score is
            <br />a starting point.
          </h3>
          <div className={s.miniScores}>
            <span>
              RAW<strong>0.84</strong>
            </span>
            <span>
              SCREENED<strong>0.00</strong>
            </span>
          </div>
          <p>
            Excluded by the occurrence-buffer rule. The original model score
            remains inspectable.
          </p>
          <h4>WHY THIS SIGNAL?</h4>
          <div className={s.shapBars}>
            <span>
              Texture representation
              <i style={{ width: "87%" }} />
            </span>
            <span>
              Terrain features
              <i style={{ width: "59%" }} />
            </span>
            <span>
              Spectral features
              <i style={{ width: "35%" }} />
            </span>
          </div>
          <small>
            Illustrative attribution layout, not measured SHAP values.
          </small>
        </aside>
      </div>
      <div className={s.scopeStatement}>
        <span>THE SCOPE GATE</span>
        <h3>
          SANDUR & BONAI RETURN NOTHING.
          <br />
          <em>NOT ZERO. NO PREDICTION.</em>
        </h3>
        <p>
          Outside validated scope (Sausar Belt). Unknown geology is not a
          negative result.
        </p>
      </div>
    </section>
  );
}
