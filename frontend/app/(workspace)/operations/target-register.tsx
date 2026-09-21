/** The Command Center's view of where to look next: the model's top greenfield
 * targets, from the same server-side ranking the Explorer draws (one cached
 * computation, lib/api/load.ts). Streamed in under <Suspense> so the vital
 * signs never wait on twenty-two backend calls.
 */

import type { CSSProperties, ReactNode } from "react";
import Link from "next/link";
import { ArrowRight, Crosshair } from "lucide-react";
import { LIVE_MODE } from "@/lib/api/client";
import { loadTopTargets } from "@/lib/api/load";
import s from "./briefing.module.css";

/** Rows shown here; the Explorer lists all of them. */
const SHOWN = 5;

function Frame({ count, children }: { count: number | null; children: ReactNode }) {
  return (
    <section className={s.reserveSection} aria-labelledby="targets-heading">
      <div className={s.reserveIntro}>
        <span className={s.reserveIcon}><Crosshair size={19} aria-hidden="true" /></span>
        <h2 id="targets-heading">Greenfield<br />target register</h2>
        <p>Where the model says to look next, on ground nobody already mines or has logged.</p>
        <div className={s.candidateCount}>
          <strong>{count === null ? "—" : String(count).padStart(2, "0")}</strong>
          <span>targets outside every<br />occurrence buffer</span>
        </div>
        <Link href="/explorer" className={s.inlineLink}>Inspect in explorer<ArrowRight size={14} /></Link>
        <p className={s.reserveCaveat}>Live model output · screening indices.<br />Not drill targets or measured ore.</p>
      </div>
      <div className={s.reserveTable}>{children}</div>
    </section>
  );
}

export function TargetRegisterFallback() {
  return (
    <Frame count={null}>
      <p role="status" className={s.footnote}>
        Ranking targets: reading the belt under the geological and occurrence-buffer masks, then asking the classifier
        for its margin at each one…
      </p>
    </Frame>
  );
}

export async function TargetRegister() {
  if (!LIVE_MODE) {
    return (
      <Frame count={null}>
        <p role="note" className={s.footnote}>
          Targets are ranked by the live model, and this build has no backend configured. No target is invented.
        </p>
      </Frame>
    );
  }
  const result = await loadTopTargets();
  if (!result.data) {
    return (
      <Frame count={null}>
        <p role="alert" className="note">Targets could not be ranked — {result.error}</p>
      </Frame>
    );
  }
  const list = result.data;
  return (
    <Frame count={list.targets.length}>
      <div className={s.tableScroll} role="region" aria-label="Greenfield target register" tabIndex={0}>
        <table className={s.places}>
          <caption className="sr-only">The model&apos;s top greenfield targets, ranked, with screening index, neighbourhood and classifier margin.</caption>
          <thead>
            <tr>
              <th scope="col">Target</th>
              <th scope="col">Screened index</th>
              <th scope="col">Neighbourhood</th>
              <th scope="col">Margin</th>
            </tr>
          </thead>
          <tbody>
            {list.targets.slice(0, SHOWN).map((target) => (
              <tr key={target.id}>
                <th scope="row">
                  <span className={s.placeName}>{target.id} · {target.label}</span>
                  <span className={s.placeKind}>
                    {target.location.latitude.toFixed(4)}° N · {target.location.longitude.toFixed(4)}° E · ± {target.precision_m} m
                  </span>
                </th>
                <td>
                  <span className={s.score} data-kind="model">
                    <span>{target.score.toFixed(2)}</span>
                    <span className={s.bar} aria-hidden="true"><i style={{ "--w": target.score } as CSSProperties} /></span>
                  </span>
                </td>
                <td className="numeric">{target.neighbourhood_score.toFixed(2)}</td>
                <td className="numeric">{target.margin === null ? "—" : `${target.margin.toFixed(2)} log-odds`}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className={s.footnote}>
        Top {Math.min(SHOWN, list.targets.length)} of {list.targets.length}. {list.ranking_note} Neighbourhood is the mean
        score of the eight surrounding cells; “—” means not measured, never zero.
      </p>
      <p className={s.footnote}>
        {list.candidates_considered} greenfield cells qualified. Targets are kept at least {list.min_separation_km} km apart
        so one anomaly cannot fill the list.
      </p>
    </Frame>
  );
}
