import localFont from "next/font/local";
import { ForecastVisual } from "./forecast-visual";
import { TerrainAtmosphere } from "./terrain-atmosphere";
import s from "./story.module.css";
import f from "./forecast.module.css";

const forecastSans = localFont({
  src: "./fonts/public-sans-latin-variable.woff2",
  weight: "400 700",
  display: "swap",
  variable: "--font-forecast",
});

export function TheForecast() {
  return (
    <section
      id="forecast"
      className={`${s.chapter} ${f.section} ${forecastSans.variable}`}
      aria-labelledby="forecast-heading"
    >
      <TerrainAtmosphere variant="waste" />
      <span className={`${s.chapterIndex} ${f.index}`} aria-hidden="true">05</span>
      <header className={f.label}>
        <span>05 / FIELD NOTES</span>
        <span>MVP 02 / HOW MUCH WILL WE DIG? / 予</span>
      </header>
      <div className={f.intro}>
        <h2 id="forecast-heading" className={f.title}>
          {"WE DON'T PROMISE."} <span>WE PREPARE.</span>
        </h2>
        <p className={f.aside}>
          The thin line is our best guess.
          <span>The wide band is how wrong we could be.</span>
        </p>
      </div>
      <div className={f.body}>
        <div className={f.text}>
          <div className={f.stanza}>
            <p>We count what came out before.</p>
            <p>We watch the rain that feeds the mines.</p>
            <p>We draw the likely next months.</p>
            <p>And we draw the bad months too — on purpose.</p>
          </div>
          <div className={f.moments}>
            <div className={f.moment}>
              <span>NEXT MONTH, COMPANY-WIDE</span>
              <strong>2,01,284 t</strong>
              <em className={f.range}>1,77,731 – 2,25,810 t</em>
              <p className={f.gloss}>80 out of 100 times, the true number lands inside this band.</p>
            </div>
            <div className={f.moment}>
              <span>CHANCE WE FALL SHORT</span>
              <strong className={f.riskValue}>
                <b data-counter="32">32</b>%
              </strong>
              <p className={`${f.gloss} ${f.riskGloss}`}>If it crosses the line, a review starts. A person decides.</p>
            </div>
          </div>
        </div>
        <figure className={f.visual}>
          <div className={f.stage}>
            <ForecastVisual />
            <span className={f.sticker}>
              HONEST FORECASTS
              <strong>RANGES, NOT PROMISES.</strong>
            </span>
          </div>
          <div className={f.legend}>
            <span><i className={f.swatchActual} aria-hidden="true" />What really happened</span>
            <span><i className={f.swatchGuess} aria-hidden="true" />Our best guess</span>
            <span><i className={f.swatchBand} aria-hidden="true" />Where the truth usually lands</span>
          </div>
          <figcaption>Schematic trajectory · Not a dated forecast. Strikes and permit disputes sit outside the model.</figcaption>
        </figure>
      </div>
      <h3 className={`${s.forecastClosing} ${f.closing}`}>
        AN INTERVAL,
        <br />
        <span className={s.outline}>NOT A PROMISE.</span>
      </h3>
    </section>
  );
}
