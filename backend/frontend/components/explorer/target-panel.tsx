"use client";

/** The model's top greenfield targets, with navigable coordinates.
 *
 * Typography and controls are the existing workspace scale only: `section-label`
 * from the survey panels, Badge for the rank, Button `link` for the disclosure
 * (as components/mines/mine-roster.tsx uses), mono `tabular-nums` for
 * coordinates. No new tokens.
 *
 * The list is fetched by ExplorerWorkspace and passed in, so the map and this
 * panel render the same ten targets from one request.
 */

import { useState } from "react";
import { Check, Copy, Crosshair, ExternalLink } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { Target, TargetList } from "@/lib/contracts";
import { useExplorerStore } from "./explorer-provider";

function coordinates(target: Target): string {
  return `${target.location.latitude.toFixed(4)}, ${target.location.longitude.toFixed(4)}`;
}

function TargetRow({
  target,
  selected,
  onSelect,
}: {
  target: Target;
  selected: boolean;
  onSelect: () => void;
}) {
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
    <li className="target-row">
      <button
        type="button"
        className="target-row-head"
        aria-expanded={selected}
        data-testid={`target-${target.id.toLowerCase()}`}
        onClick={onSelect}
      >
        <Badge variant={target.rank <= 3 ? "default" : "secondary"}>{target.id}</Badge>
        <span className="target-row-label">{target.label}</span>
        {/* The score is capped and identical across the shortlist; the margin
            is what separates them, so both are shown. */}
        <span className="target-row-numbers font-mono text-xs tabular-nums">
          <span>{target.score.toFixed(2)}</span>
          {target.margin !== null && (
            <span className="target-row-margin">{target.margin.toFixed(1)}</span>
          )}
        </span>
      </button>
      {selected && (
        <div className="target-row-detail">
          <p className="font-mono text-xs tabular-nums">{text}</p>
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
              <dd>
                {Math.round(target.km_to_nearest_mine)} km {target.bearing_from_mine} of{" "}
                {target.nearest_mine}
              </dd>
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
                  {target.raw_probability !== null
                    ? ` · p ${target.raw_probability.toFixed(3)} uncapped`
                    : ""}
                </dd>
              </div>
            )}
            <div>
              <dt>Coordinate precision</dt>
              <dd>± {target.precision_m} m</dd>
            </div>
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

export function TargetPanel({
  list,
  loading,
  error,
}: {
  list: TargetList | null;
  loading: boolean;
  error: string | null;
}) {
  const selected = useExplorerStore((s) => s.selected);
  const select = useExplorerStore((s) => s.select);

  return (
    <div className="target-panel">
      <div className="survey-intro">
        <p className="section-label">
          <Crosshair size={13} aria-hidden="true" /> Model targets
        </p>
        <p className="text-xs leading-5 text-muted-foreground">
          The ten highest-scoring places the model picks out on ground nobody is already mining.
          Shortlisted by how strongly the surrounding cells score — a lone hot cell beside cold
          ground is more likely noise than a deposit — then ordered by the classifier&apos;s
          margin, the small grey figure, because the score beside it is capped.
        </p>
      </div>

      {loading && (
        <p className="note" role="status">
          Scoring the belt and refining each target…
        </p>
      )}
      {error && (
        <p className="note" role="alert">
          Targets unavailable — {error}
        </p>
      )}

      {list && (
        <>
          <ul className="target-list">
            {list.targets.map((target) => (
              <TargetRow
                key={target.id}
                target={target}
                selected={selected?.kind === "target" && selected.id === target.id}
                onSelect={() =>
                  select(
                    selected?.kind === "target" && selected.id === target.id
                      ? null
                      : { kind: "target", id: target.id },
                  )
                }
              />
            ))}
          </ul>
          <p className="note">
            Screening indices, not drill targets. {list.candidates_considered} cells qualified, and
            every one of these sits at the {list.targets[0]?.score.toFixed(2)} cap: the Elkan-Noto
            adjustment divides by 0.905 and the cap then pins anything above a raw 0.896, so the
            score cannot separate them. The second figure is the classifier&apos;s margin in
            log-odds, which does, and the order follows it. Shortlisting used neighbourhood
            coherence, and targets are kept at least {list.min_separation_km} km apart so one
            anomaly cannot fill the list.
          </p>
        </>
      )}
    </div>
  );
}
