import { ChapterLabel } from "./shared";
import s from "./story.module.css";
export function TheDecision() {
  return (
    <section
      className={s.chapter + " " + s.paper + " " + s.decision}
      aria-labelledby="decision-heading"
    >
      <ChapterLabel number="06">MVP 03 / CORRECTIVE ACTIONS / 決</ChapterLabel>
      <div className={s.twoColumn}>
        <div>
          <h2 id="decision-heading" className={s.display}>
            The human
            <br />
            has the
            <br />
            last word.
          </h2>
          <p className={s.lead}>
            The system never acts.
            <br />
            It recommends. People decide.
          </p>
        </div>
        <article className={s.ruleSheet} data-card>
          <div className={s.sheetHeading}>
            <span>RULE / OPS–WATER–01</span>
            <span>ILLUSTRATIVE</span>
          </div>
          <h3>
            Review drainage
            <br />
            and pump capacity.
          </h3>
          <p>
            Inspect water handling before a forecast period of elevated
            rainfall. A rule proposes review; it does not authorize expenditure.
          </p>
          <div className={s.tableScroll}>
            <table>
              <caption>Example trigger clauses</caption>
              <thead>
                <tr>
                  <th>Feature</th>
                  <th>Value</th>
                  <th>Operator</th>
                  <th>Threshold</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td>Rainfall category</td>
                  <td>High</td>
                  <td>=</td>
                  <td>High</td>
                </tr>
                <tr>
                  <td>Drainage review</td>
                  <td>Pending</td>
                  <td>=</td>
                  <td>Pending</td>
                </tr>
              </tbody>
            </table>
          </div>
          <div className={s.reviewStamp} data-stamp>
            PROPOSED<span>HUMAN REVIEW REQUIRED</span>
          </div>
          <footer>
            Evidence → recommendation → assigned reviewer → recorded decision
          </footer>
        </article>
      </div>
    </section>
  );
}
