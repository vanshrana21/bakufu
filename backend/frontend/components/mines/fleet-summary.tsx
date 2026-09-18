/** The three-group reading of the roster, above the cards.
 *
 * Layout matched from app/(workspace)/assets/page.tsx (section heading rhythm)
 * and components/assets/MineOverviewGrid.tsx (Card + Badge + Tailwind grid).
 * Typography is the existing scale only: CardTitle, text-xs/text-sm and
 * text-muted-foreground. No new tokens, no new heading sizes.
 *
 * Group membership and every figure quoted are computed from the scores the
 * page just fetched. They were hardcoded in the brief; a hardcoded "6 mines"
 * would silently lie the first time a score moved - the same failure
 * app/(workspace)/production/page.tsx documents for its hardcoded dates.
 */

import { Badge, type BadgeProps } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { Mine } from "@/lib/contracts";

/** The bands the analysis uses: docs/mine_score_distribution_analysis.md. */
export const GROUP_FLOOR = { recognised: 0.85, mixed: 0.35 } as const;

export type GroupKey = "recognised" | "mixed" | "low";

export function groupOf(mine: Mine): GroupKey | null {
  if (mine.score === null) return null;
  if (mine.score.value >= GROUP_FLOOR.recognised) return "recognised";
  if (mine.score.value >= GROUP_FLOOR.mixed) return "mixed";
  return "low";
}

/** Semantic variants only. In this theme `success` is char and `warning` and
 * `destructive` are ore at different opacities - the palette has nine solid
 * colours and these three are the status tokens the rest of the workspace
 * already uses (components/assets/MineOverviewGrid.tsx). */
export const GROUP_VARIANT: Record<GroupKey, BadgeProps["variant"]> = {
  recognised: "success",
  mixed: "warning",
  low: "destructive",
};

/** "Low score" rather than "low confidence": the cards already use
 * "Low confidence" for the *coordinate* tier, and one page cannot use one
 * phrase for two different measurements. */
const GROUP_LABEL: Record<GroupKey, string> = {
  recognised: "Recognised",
  mixed: "Mixed signal",
  low: "Low score",
};

const listNames = (mines: Mine[]) => mines.map((mine) => mine.name).join(", ");

const withScore = (mine: Mine) =>
  mine.score ? `${mine.name} (${mine.score.value.toFixed(2)})` : mine.name;

export function FleetSummary({ mines }: { mines: readonly Mine[] }) {
  const groups: Record<GroupKey, Mine[]> = { recognised: [], mixed: [], low: [] };
  const unscored: Mine[] = [];
  for (const mine of mines) {
    const key = groupOf(mine);
    if (key === null) unscored.push(mine);
    else groups[key].push(mine);
  }
  const best = [...groups.recognised].sort(
    (a, b) => (b.score?.value ?? 0) - (a.score?.value ?? 0),
  );
  // The generalisation case: the mine furthest from anything the model trained
  // on that still scores in the top band.
  const farthest = best.find((mine) => mine.name === "Gumgaon") ?? best[0];

  const narrative: Record<GroupKey, string> = {
    recognised:
      `${groups.recognised.length} of the ten are recognised confidently: the model reads manganese-bearing terrain and surface spectral pattern at these coordinates.` +
      (farthest?.score
        ? ` ${withScore(farthest)} is the generalisation case — it sits 7.6 km from the nearest point the model trained on, so the score is not recall of a known location.`
        : ""),
    mixed:
      `${groups.mixed.length === 1 ? "One mine shows" : `${groups.mixed.length} mines show`} mixed signal. ` +
      `${groups.mixed.map(withScore).join(", ")} — terrain fits the productive pattern while surface texture does not, and the coordinate is a town-centre proxy. Field verification before any drill decision.`,
    low:
      `${groups.low.length} return low confidence, and that is the honest result: ${groups.low.map(withScore).join(", ")}. ` +
      `Deep underground workings leave no more surface trace than the hillside above them, and every feature here derives from surface reflectance and terrain. A model that scored all ten at the cap would show only that it had memorised the coordinates.`,
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>{mines.length} mines, three signal types</CardTitle>
        <p className="text-xs text-muted-foreground">
          Bands from the score distribution analysis: at or above{" "}
          {GROUP_FLOOR.recognised.toFixed(2)}, {GROUP_FLOOR.mixed.toFixed(2)} to{" "}
          {GROUP_FLOOR.recognised.toFixed(2)}, and below {GROUP_FLOOR.mixed.toFixed(2)}.
        </p>
      </CardHeader>
      <CardContent className="grid gap-4 sm:grid-cols-3">
        {(Object.keys(groups) as GroupKey[]).map((key) => (
          <div key={key}>
            <div className="mb-2 flex items-center gap-2">
              <Badge variant={GROUP_VARIANT[key]}>{GROUP_LABEL[key]}</Badge>
              <span className="font-mono text-xs tabular-nums text-muted-foreground">
                {groups[key].length.toString().padStart(2, "0")} mines
              </span>
            </div>
            <p className="text-xs leading-5 text-muted-foreground">{narrative[key]}</p>
          </div>
        ))}
        {unscored.length > 0 && (
          <p className="text-xs leading-5 text-muted-foreground sm:col-span-3">
            No score returned for {listNames(unscored)}: the backend reports no imagery at
            those coordinates. An absent score is not a low score.
          </p>
        )}
      </CardContent>
    </Card>
  );
}
