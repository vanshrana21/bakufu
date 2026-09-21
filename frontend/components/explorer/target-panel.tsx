/** The model's top greenfield exploration targets beside the known mines.
 *
 * A Server Component streamed in under <Suspense>: the ranking takes twenty-two
 * backend calls, so it runs on the server with the API key (no proxy budget to
 * exhaust, nothing exposed to the browser) and the map paints without waiting
 * for it. */

import { LIVE_MODE } from "@/lib/api/client";
import { loadMineLocations, loadTopTargets } from "@/lib/api/load";
import { BeltLocator } from "@/components/mines/belt-locator";
import s from "@/components/mines/mines.module.css";

function Heading({ tag }: { tag?: string }) {
  return (
    <div className={s.targetsHead}>
      <div>
        <h2 id="targets-heading">Top greenfield targets</h2>
        <p>
          Where the model reads the strongest coherent signal on basement ground that no known occurrence explains —
          outside every 5 km buffer, at least 10 km apart. Candidates for a field visit, not proven ore.
        </p>
      </div>
      {tag && <span className={s.rankingTag}>{tag}</span>}
    </div>
  );
}

export function TargetPanelFallback() {
  return (
    <section className={s.targets} aria-labelledby="targets-heading" aria-busy="true">
      <Heading />
      <p className={s.targetsState} role="status">
        Ranking targets: reading the belt under the geological and occurrence-buffer masks, refining each winner to
        ~350 m, then asking the classifier for its margin at each one…
      </p>
    </section>
  );
}

export async function TargetPanel() {
  if (!LIVE_MODE) {
    return (
      <section className={s.targets} aria-labelledby="targets-heading">
        <Heading />
        <p className={s.targetsState} role="note">
          Targets are ranked by the live model; this demonstration build has no backend, and no target is invented.
        </p>
      </section>
    );
  }

  const [result, mines] = await Promise.all([loadTopTargets(), loadMineLocations()]);
  if (!result.data) {
    return (
      <section className={s.targets} aria-labelledby="targets-heading">
        <Heading />
        <p className={s.targetsState} data-state="error" role="alert">Targets could not be ranked — {result.error}</p>
      </section>
    );
  }

  const data = result.data;
  return (
    <section className={s.targets} aria-labelledby="targets-heading">
      <Heading tag={data.ranking === "classifier_margin" ? "Ranked by classifier margin" : "Ranked by neighbourhood coherence"} />
      <BeltLocator
        caption={`${data.targets.length} targets (numbered circles) and the MOIL mines (diamonds) at their true positions`}
        points={[
          ...(mines.data ?? []).map((mine) => ({
            id: `mine-${mine.name}`,
            label: mine.name,
            latitude: mine.location.latitude,
            longitude: mine.location.longitude,
            kind: "mine" as const,
          })),
          ...data.targets.map((target) => ({
          id: target.id,
          label: `${target.id} · ${target.label}`,
          latitude: target.location.latitude,
          longitude: target.location.longitude,
          kind: "target" as const,
          rank: target.rank,
        })),
        ]}
      />
      <div>
        <table className={s.targetTable}>
          <caption className="sr-only">Top greenfield targets, ranked</caption>
          <thead>
            <tr>
              <th scope="col">#</th>
              <th scope="col">Where</th>
              <th scope="col">Score</th>
              <th scope="col">Nbhd</th>
              <th scope="col">Margin</th>
            </tr>
          </thead>
          <tbody>
            {data.targets.map((target) => (
              <tr key={target.id}>
                <td><span className={s.rank}>{target.rank}</span></td>
                <th scope="row" style={{ fontWeight: 500 }}>
                  {target.label}
                  <span className={s.coord}>
                    {target.location.latitude.toFixed(4)}° N · {target.location.longitude.toFixed(4)}° E · ±{Math.round(target.precision_m / 2)} m
                  </span>
                </th>
                <td className={s.num} data-kind="model">{target.score.toFixed(2)}</td>
                <td className={s.num}>{target.neighbourhood_score.toFixed(2)}</td>
                <td className={s.num}>{target.margin === null ? "—" : target.margin.toFixed(2)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className={s.targetsFoot}>
        {data.ranking_note} {data.candidates_considered} greenfield cells were considered. Score is the served screening
        index (capped at 0.99); Nbhd is the mean of the eight surrounding cells; “—” means not measured, never zero.
      </p>
    </section>
  );
}
