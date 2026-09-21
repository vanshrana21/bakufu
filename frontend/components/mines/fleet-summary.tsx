/** The fleet at a glance: where the ten mines lie, and which band the model
 * reads each one in. Every count is computed from the scores this render
 * fetched — a hardcoded "six recognised" would lie the first time a score moved. */

import type { Mine } from "@/lib/contracts";
import { BeltLocator } from "./belt-locator";
import { BAND_FLOOR, BAND_LABEL, bandOf, type Band } from "./mine-card";
import s from "./mines.module.css";

const RULE: Record<Band, string> = {
  recognised: `≥ ${BAND_FLOOR.recognised.toFixed(2)}`,
  mixed: `${BAND_FLOOR.mixed.toFixed(2)} – ${BAND_FLOOR.recognised.toFixed(2)}`,
  low: `< ${BAND_FLOOR.mixed.toFixed(2)}`,
  unscored: "no score",
};

export function FleetSummary({ mines }: { mines: readonly Mine[] }) {
  const bands: Record<Band, Mine[]> = { recognised: [], mixed: [], low: [], unscored: [] };
  for (const mine of mines) bands[bandOf(mine)].push(mine);
  const order: Band[] = bands.unscored.length ? ["recognised", "mixed", "low", "unscored"] : ["recognised", "mixed", "low"];

  return (
    <section className={s.summary} aria-labelledby="fleet-summary-heading">
      <BeltLocator
        caption="Sausar Belt · each mine at its cited coordinate, filled by how strongly the model reads it"
        points={mines.map((mine) => ({
          id: mine.name,
          label: mine.name,
          latitude: mine.location.latitude,
          longitude: mine.location.longitude,
          kind: "mine" as const,
          band: bandOf(mine),
        }))}
      />
      <div className={s.bands}>
        <h2 id="fleet-summary-heading" className="section-label">How the model reads the fleet</h2>
        {order.map((band) => (
          <div key={band} className={s.bandRow} data-band={band}>
            <strong>{String(bands[band].length).padStart(2, "0")}</strong>
            <div>
              <p className={s.bandName}>{BAND_LABEL[band]} <span>{RULE[band]}</span></p>
              <p className={s.bandMembers}>
                {bands[band].length
                  ? bands[band].map((mine) => mine.score ? `${mine.name} ${mine.score.value.toFixed(2)}` : mine.name).join(" · ")
                  : "None"}
              </p>
            </div>
          </div>
        ))}
        <p className={s.bandNote}>
          A score is a screening index read at one cited coordinate. It is not a reserve estimate, and a low
          score at an operating mine says the surface there does not look like the ground the model learned from.
        </p>
      </div>
    </section>
  );
}
