import { ChapterLabel } from "./shared";
import { CellField } from "./cell-field";
import s from "./story.module.css";
import m from "./map.module.css";
export function TheMap() {
  return (
    <section
      className={s.chapter + " " + s.paper + " " + s.mapChapter}
      data-pin="map"
      aria-labelledby="map-heading"
    >
      <ChapterLabel number="04">
        MVP 01 / THE MAP THAT POINTS
      </ChapterLabel>
      <div className={s.sectionIntro}>
        <h2 id="map-heading" className={s.display}>
          EVERY BLOCK
          <br />
          GETS CHECKED.
        </h2>
        <p>
          A hot spot is not a yes.
          <br />
          It is a place to look closer.
        </p>
      </div>
      <div className={s.mapLayout}>
        <figure className={s.cellFigure}>
          <CellField />
          <figcaption>32 × 32 example blocks · Not a real map</figcaption>
          <div className={s.cellLegend}>
            <span>
              <i />
              Darker = higher score
            </span>
            <span>
              <i className={s.hatchedKey} />
              Removed by rules
            </span>
            <span>
              <i className={s.nullKey} />
              {"We don't guess here"}
            </span>
            <span>◇ Model target</span>
          </div>
        </figure>
        <aside className={`${s.mapInspector} ${m.inspector}`}>
          <span className={s.mono}>SELECTED EXAMPLE / T–01</span>
          <h3>A score only tells you where to look.</h3>
          <div className={s.miniScores}>
            <span>
              FIRST SCORE<strong>0.84</strong>
            </span>
            <span>
              AFTER RULES<strong className={m.struck}>0.00</strong>
            </span>
          </div>
          <p>
            This site scored high. A protection rule removed it anyway. The old
            score stays on the page so you can check our work.
          </p>
          <h4>WHY DID IT SCORE HIGH?</h4>
          <div className={s.shapBars}>
            <span>
              What the surface looks like
              <i style={{ width: "87%" }} />
            </span>
            <span>
              The shape of the land
              <i style={{ width: "59%" }} />
            </span>
            <span>
              What the satellite colours show
              <i style={{ width: "35%" }} />
            </span>
          </div>
          <small>Example bars, not measured values.</small>
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
          {"These places are outside our study area. 'We don't know' is not the same as 'nothing is there.'"}
        </p>
      </div>
    </section>
  );
}
