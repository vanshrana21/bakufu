"use client";

/** The model's top greenfield targets, with navigable coordinates.
 *
 * The ranking is computed on the server (components/explorer/targets-feed.tsx)
 * and streamed into the Explorer store, so the map and this list render the
 * same ten targets from one computation. Ported from the team lead's Explorer
 * (yashnimde-ship-it/Spin-off, 35e464a, 0f99c67).
 */

import { useState } from "react";
import { Check, Copy, Crosshair, ExternalLink } from "lucide-react";
import { Button } from "@/components/ui/button";
import type { Target } from "@/lib/contracts";
import { useExplorerStore } from "./explorer-provider";

const coordinates = (target: Target) =>
  `${target.location.latitude.toFixed(4)}, ${target.location.longitude.toFixed(4)}`;

function TargetRow({ target, selected, onSelect }: { target: Target; selected: boolean; onSelect: () => void }) {
  const [copied, setCopied] = useState(false);
  const text = coordinates(target);

  async function copy() {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      // Clipboard can be blocked; the coordinate is on screen to read off.
    }
  }

  return (
    <li className="target-row" data-selected={selected}>
      <button
        type="button"
        className="target-row-head"
        aria-expanded={selected}
        data-testid={`target-${target.id.toLowerCase()}`}
        onClick={onSelect}
      >
        <span className="target-row-rank" data-top={target.rank <= 3}>{target.id}</span>
        <span className="target-row-label">{target.label}</span>
        {/* The score is capped and identical across the shortlist; the margin
            is what separates them, so both are shown. */}
        <span className="target-row-numbers">
          <span data-kind="model">{target.score.toFixed(2)}</span>
          {target.margin !== null && <span className="target-row-margin">{target.margin.toFixed(1)}</span>}
        </span>
      </button>
      {selected && (
        <div className="target-row-detail">
          <p className="font-mono text-xs tabular-nums">{text} · ± {target.precision_m} m</p>
          <div className="target-row-actions">
            <Button variant="outline" size="sm" onClick={copy}>
              {copied ? <Check size={13} aria-hidden="true" /> : <Copy size={13} aria-hidden="true" />}
              {copied ? "Copied" : "Copy"}
            </Button>
            <Button variant="outline" size="sm" asChild>
              <a
                href={`https://www.google.com/maps/search/?api=1&query=${target.location.latitude},${target.location.longitude}`}
                target="_blank"
                rel="noreferrer"
              >
                <ExternalLink size={13} aria-hidden="true" />
                Open in Maps
              </a>
            </Button>
          </div>
          <dl className="target-row-facts">
            <div>
              <dt>Distance</dt>
              <dd>{Math.round(target.km_to_nearest_mine)} km {target.bearing_from_mine} of {target.nearest_mine}</dd>
            </div>
            <div>
              <dt>Neighbourhood</dt>
              <dd>{target.neighbourhood_score.toFixed(2)} mean of adjacent cells</dd>
            </div>
            {target.margin !== null && (
              <div>
                <dt>Classifier margin</dt>
                <dd>
                  {target.margin.toFixed(2)} log-odds
                  {target.raw_probability !== null ? ` · p ${target.raw_probability.toFixed(3)} uncapped` : ""}
                </dd>
              </div>
            )}
            <div>
              <dt>Status</dt>
              <dd>Outside the 5 km occurrence buffer</dd>
            </div>
          </dl>
        </div>
      )}
    </li>
  );
}

export function TargetPanel() {
  const state = useExplorerStore((s) => s.targets);
  const selected = useExplorerStore((s) => s.selected);
  const select = useExplorerStore((s) => s.select);

  return (
    <section className="target-panel" aria-labelledby="targets-heading" aria-busy={state.status === "loading"}>
      <div className="target-panel-intro">
        <h2 id="targets-heading" className="section-label">
          <Crosshair size={13} aria-hidden="true" /> Model targets
        </h2>
        <p>
          The ten strongest places the model picks out on ground nobody already mines or has logged: outside every
          5 km occurrence buffer, at least 10 km apart. Candidates for a field visit, not proven ore.
        </p>
      </div>

      {state.status === "loading" && (
        <p className="note" role="status">
          Ranking targets: reading the belt under the geological and occurrence-buffer masks, refining each winner,
          then asking the classifier for its margin at each one…
        </p>
      )}
      {state.status === "unavailable" && <p className="note" role="alert">{state.reason}</p>}

      {state.status === "ready" && (
        <>
          <ul className="target-list">
            {state.list.targets.map((target) => (
              <TargetRow
                key={target.id}
                target={target}
                selected={selected?.kind === "target" && selected.id === target.id}
                onSelect={() =>
                  select(selected?.kind === "target" && selected.id === target.id ? null : { kind: "target", id: target.id })
                }
              />
            ))}
          </ul>
          <p className="target-panel-foot">
            {state.list.ranking === "classifier_margin"
              ? `Every target reads the ${state.list.targets[0]?.score.toFixed(2) ?? "0.99"} cap, so they are ordered by the classifier's margin in log-odds (the small grey figure). `
              : `${state.list.ranking_note} `}
            {state.list.candidates_considered} greenfield cells qualified; shortlisted by how strongly their neighbours
            also score, so a lone hot pixel beside cold ground does not make the list.
          </p>
        </>
      )}
    </section>
  );
}
