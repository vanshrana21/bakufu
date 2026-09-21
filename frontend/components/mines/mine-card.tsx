/** One mine: the model's read of its cited coordinate, and how far that
 * coordinate can be trusted. Server-rendered; nothing here fetches. */

import type { Mine } from "@/lib/contracts";
import { tonnes } from "@/lib/format";
import s from "./mines.module.css";

/** The analysis bands (backend/docs/mine_score_distribution_analysis.md). */
export const BAND_FLOOR = { recognised: 0.85, mixed: 0.35 } as const;
export type Band = "recognised" | "mixed" | "low" | "unscored";

export function bandOf(mine: Mine): Band {
  if (!mine.score) return "unscored";
  if (mine.score.value >= BAND_FLOOR.recognised) return "recognised";
  if (mine.score.value >= BAND_FLOOR.mixed) return "mixed";
  return "low";
}

export const BAND_LABEL: Record<Band, string> = {
  recognised: "Recognised",
  mixed: "Mixed signal",
  // "Low score", not "low confidence": the card already uses confidence for the
  // coordinate, and one page cannot use one phrase for two measurements.
  low: "Low score",
  unscored: "Not scored",
};

const humanise = (value: string) => value.replaceAll("_", " ");
const confidenceLabel = (value: string) =>
  value.split("_").map((part) => part.charAt(0).toUpperCase() + part.slice(1)).join("–");

export function MineCard({ mine }: { mine: Mine }) {
  const band = bandOf(mine);
  const drivers = mine.score
    ? [...mine.score.drivers].sort((a, b) => Math.abs(b.contribution) - Math.abs(a.contribution)).slice(0, 3)
    : [];
  const { latitude, longitude } = mine.location;
  return (
    <article className={s.card} data-band={band} aria-labelledby={`mine-${mine.name}`}>
      <header className={s.cardHead}>
        <div>
          <h3 id={`mine-${mine.name}`}>{mine.name}</h3>
          <p>{mine.district}, {mine.state}</p>
        </div>
        <span className={s.typeChip}>{humanise(mine.mine_type)}</span>
      </header>

      {mine.score ? (
        <div className={s.scoreBlock}>
          <div className={s.scoreRow}>
            <strong data-kind="model">{mine.score.value.toFixed(2)}</strong>
            <span className={s.bandTag} data-band={band}>{BAND_LABEL[band]}</span>
          </div>
          <div className={s.scoreBar} aria-hidden="true"><i style={{ width: `${(mine.score.value / 0.99) * 100}%` }} /></div>
          <p className={s.scoreMeta}>
            Screening index at the cited point, 0–0.99
            {mine.score.margin !== null && <> · classifier margin {mine.score.margin.toFixed(2)}</>}
          </p>
        </div>
      ) : (
        <p className={s.unscored} role="note">{mine.score_unavailable}</p>
      )}

      {drivers.length > 0 && (
        <ul className={s.drivers} aria-label={`What moved ${mine.name}'s score`}>
          {drivers.map((driver) => (
            <li key={driver.label} data-direction={driver.contribution >= 0 ? "up" : "down"}>
              <span aria-hidden="true">{driver.contribution >= 0 ? "▲" : "▼"}</span>
              {driver.label}
              <em>{driver.contribution >= 0 ? "+" : "−"}{Math.abs(driver.contribution).toFixed(2)}</em>
            </li>
          ))}
        </ul>
      )}

      <dl className={s.facts}>
        <div>
          <dt>Cited coordinate</dt>
          <dd className={s.mono}>{latitude.toFixed(4)}° N · {longitude.toFixed(4)}° E</dd>
        </div>
        <div>
          <dt>Coordinate confidence</dt>
          <dd><span className={s.confidence} data-confidence={mine.coordinate.confidence}>{confidenceLabel(mine.coordinate.confidence)}</span></dd>
        </div>
        <div className={s.factWide}>
          <dt>Source</dt>
          <dd>
            {mine.coordinate.source_url
              ? <a href={mine.coordinate.source_url} target="_blank" rel="noreferrer">{mine.coordinate.source}</a>
              : mine.coordinate.source}
          </dd>
        </div>
        {mine.capacity_target_tonnes !== null && (
          <div>
            <dt>Capacity target</dt>
            <dd className={s.mono}>{tonnes(mine.capacity_target_tonnes)} t</dd>
          </div>
        )}
      </dl>

      {mine.coordinate.note && <p className={s.note}>{mine.coordinate.note}</p>}
      {mine.caveat && <p className={s.caveat}><span>Read with care</span>{mine.caveat}</p>}

      {mine.equipment.length > 0 && (
        <ul className={s.equipment} aria-label="Equipment on record">
          {mine.equipment.map((item) => <li key={item}>{humanise(item)}</li>)}
        </ul>
      )}
    </article>
  );
}
