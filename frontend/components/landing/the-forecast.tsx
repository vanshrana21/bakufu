import { ChapterLabel } from "./shared";
import s from "./story.module.css";
export function TheForecast() {
  return (
    <section
      className={s.chapter + " " + s.forecast}
      data-pin="forecast"
      aria-labelledby="forecast-heading"
    >
      <ChapterLabel number="05">MVP 02 / PRODUCTION & RISK / 予</ChapterLabel>
      <div className={s.sectionIntro}>
        <h2 id="forecast-heading" className={s.display}>
          SEE THE
          <br />
          <span className={s.heavy}>SHORTFALL.</span>
        </h2>
        <p>
          Company-wide production.
          <br />A range of futures, not a prophecy.
        </p>
      </div>
      <div className={s.forecastLayout}>
        <figure>
          <svg
            className={s.forecastChart}
            viewBox="0 0 800 320"
            role="img"
            aria-label="Illustrative production trajectory with a dashed forecast and widening 80 percent prediction interval; not live production data"
          >
            {[60, 120, 180, 240].map((y) => (
              <path key={y} d={"M20 " + y + "H780"} stroke="#362C2A" />
            ))}
            <path
              data-band
              d="M485 161 550 129 620 96 690 60 770 24V160L690 179 620 192 550 181 485 161Z"
              fill="#D39858"
              fillOpacity=".25"
            />
            <path
              data-history
              d="M20 246 75 237 130 255 185 205 240 218 295 169 350 185 405 143 450 179 485 161"
              fill="none"
              stroke="#EACEAA"
              strokeWidth="3"
            />
            <path
              data-future
              d="M485 161 550 154 620 142 690 119 770 93"
              fill="none"
              stroke="#D39858"
              strokeWidth="3"
              strokeDasharray="9 7"
            />
            <path d="M485 20V280" stroke="#EACEAA" strokeOpacity=".5" strokeDasharray="3 5" />
            <circle cx="485" cy="161" r="6" fill="#D39858" />
            <g fill="#EACEAA" fillOpacity=".7" fontSize="12" fontFamily="monospace">
              <text x="20" y="309">
                HISTORICAL OBSERVATIONS
              </text>
              <text x="470" y="309">
                ISSUE DATE
              </text>
              <text x="660" y="309">
                FORECAST →
              </text>
            </g>
          </svg>
          <figcaption className={s.forecastLegend}>
            <span>— Actual</span>
            <span className={s.limeText}>- - Forecast</span>
            <span>▨ 80% prediction interval</span>
          </figcaption>
          <p className={s.footnote}>
            Schematic trajectory, not a dated forecast. Sudden strikes, failures
            and permit disputes may be outside the model’s features.
          </p>
        </figure>
        <aside className={s.riskAside}>
          <div className={s.riskRing}>
            <svg viewBox="0 0 160 160" aria-hidden="true">
              <circle
                cx="80"
                cy="80"
                r="65"
                fill="none"
                stroke="#362C2A"
                strokeWidth="13"
              />
              <circle
                data-risk
                cx="80"
                cy="80"
                r="65"
                fill="none"
                stroke="var(--ore)"
                strokeWidth="13"
                pathLength="100"
                strokeDasharray="32 100"
                transform="rotate(-90 80 80)"
              />
            </svg>
            <strong>
              32<span>%</span>
            </strong>
          </div>
          <span className={s.mono}>ILLUSTRATIVE RISK</span>
          <p>
            Probability of output falling below 90% of the issued forecast. The
            event definition travels with the score.
          </p>
        </aside>
      </div>
      <h3 className={s.forecastClosing}>
        AN INTERVAL,
        <br />
        <span className={s.outline}>NOT A PROMISE.</span>
      </h3>
    </section>
  );
}
