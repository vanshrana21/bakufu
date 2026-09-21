/** Streams the ranked greenfield targets into the Explorer.
 *
 * A Server Component rendered under <Suspense>: the ranking takes twenty-two
 * backend calls, so it runs on the server with the API key (no browser proxy
 * budget to exhaust, nothing exposed to the browser), and the map, the surface
 * and the mines paint without waiting for it. When it resolves, the hydrator
 * hands the result to the Explorer store, where the map markers and the target
 * list both read it.
 */

import { LIVE_MODE } from "@/lib/api/client";
import { loadTopTargets } from "@/lib/api/load";
import { TargetsHydrator } from "./targets-hydrator";

export async function TargetsFeed() {
  if (!LIVE_MODE) {
    return (
      <TargetsHydrator
        state={{ status: "unavailable", reason: "Targets are ranked by the live model, and this build has no backend configured. No target is invented." }}
      />
    );
  }
  const result = await loadTopTargets();
  return (
    <TargetsHydrator
      state={result.data
        ? { status: "ready", list: result.data }
        : { status: "unavailable", reason: `Targets could not be ranked — ${result.error}` }}
    />
  );
}
