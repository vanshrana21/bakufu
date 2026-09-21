/** Adapter for GET /mines, each mine scored through POST /predict/point.
 *
 * Server-only: the Mine Fleet page and the Explorer page call this from their
 * Server Components, so `/mines` never needs the browser proxy. The roster and
 * the scores come from two endpoints on purpose: /mines carries the cited
 * coordinate and how far it can be trusted, /predict/point carries the model's
 * read of that exact point. They are fetched together so a card can never show
 * a score without the provenance of the point it was taken at.
 */

import type { Mine, MineLocation, MineRoster, MineScore } from "@/lib/contracts";
import { MineLocationSchema, MineRosterSchema } from "@/lib/contracts";
import type { WireMine, WireMines, WirePredictPoint } from "./wire";
import { ApiRequestError, PREDICT_POINT_TIMEOUT_MS, apiGet, apiPost } from "./client";
import { parseWire, WireMinesSchema, WirePredictPointSchema } from "./wire-schemas";

const STATE_NAMES: Record<string, string> = { MH: "Maharashtra", MP: "Madhya Pradesh" };

/** Per-mine cautions. Each states a measured fact from the backend's own
 * analyses (backend/docs/mine_score_distribution_analysis.md and
 * moil_coordinate_sources.md), and none depends on how the mines rank today,
 * so a moved score cannot make one of them false. */
export const MINE_CAVEATS: Readonly<Record<string, string>> = {
  Balaghat:
    "Deep underground workings: imagery reads surface reflectance and terrain, not ore at depth. " +
    "Point scores swing at this resolution — a 5 × 5 grid within ±2 km of this coordinate runs 0.02 to 0.99 — " +
    "so read the heatmap cell, not the point.",
  "Dongri Buzurg":
    "The cited coordinate is Dongri Buzurg railway station, a proxy 1–2 km from the workings, " +
    "so the scored pixel may not be the pit.",
  Tirodi: "The cited coordinate is a town-centre proxy, not a lease boundary, so the scored pixel may miss the workings.",
  Sitapatore: "The coordinate comes from a MOIL Mining Plan point rather than a surveyed lease boundary.",
};

export const fetchMines = (signal?: AbortSignal): Promise<WireMines> =>
  apiGet<unknown>("/mines", { signal })
    .then((raw) => parseWire(WireMinesSchema, raw, "/mines"));

/** One mine's score, or the reason it has none. A 404 is the backend's honest
 * "no imagery at this coordinate" and must reach the card as a stated absence,
 * never as a zero. */
async function scoreMine(mine: WireMine, signal?: AbortSignal): Promise<{ score: WirePredictPoint | null; error: string | null }> {
  try {
    const raw = await apiPost<unknown>(
      "/predict/point",
      { lat: mine.lat, lon: mine.lon },
      // Unmasked on purpose: a known mine sits inside its own occurrence buffer,
      // so the masks would only restate that. The raw model read is the point.
      { signal, query: { mask: "none" }, timeoutMs: PREDICT_POINT_TIMEOUT_MS },
    );
    return { score: parseWire(WirePredictPointSchema, raw, "/predict/point"), error: null };
  } catch (error) {
    if (error instanceof ApiRequestError) {
      return {
        score: null,
        error: error.status === 404 ? "No Sentinel-2 imagery at this coordinate, so the model has nothing to read." : error.message,
      };
    }
    return { score: null, error: error instanceof Error ? error.message : "The model could not score this coordinate." };
  }
}

function scoreFrom(wire: WirePredictPoint): MineScore {
  return {
    value: Math.min(Math.max(wire.raw_score ?? wire.prospectivity_score, 0), 0.99),
    raw_probability: wire.raw_probability ?? null,
    margin: wire.model_margin ?? null,
    drivers: wire.shap_top5.map((row) => ({
      label: row.feature.replaceAll("_", " "),
      contribution: row.shap_value,
      value: row.actual_value,
    })),
    model_version: wire.model_version,
  };
}

export function adaptMine(mine: WireMine, scored: { score: WirePredictPoint | null; error: string | null } | null): Mine {
  return {
    name: mine.mine_name,
    state: STATE_NAMES[mine.state] ?? mine.state,
    district: mine.district,
    mine_type: mine.mine_type,
    location: { longitude: mine.lon, latitude: mine.lat },
    coordinate: {
      confidence: mine.confidence,
      source: mine.source,
      source_url: mine.source_url,
      precision: mine.coordinate_precision,
      note: mine.coordinate_note,
    },
    equipment: mine.equipment,
    capacity_target_tonnes: mine.capacity_target_tonnes,
    notes: mine.notes,
    score: scored?.score ? scoreFrom(scored.score) : null,
    score_unavailable: scored === null
      ? "Scores come from the live model; this demonstration build has no backend."
      : scored.score ? null : (scored.error ?? "The model could not score this coordinate."),
    caveat: MINE_CAVEATS[mine.mine_name] ?? null,
  };
}

function countsOf(mines: readonly WireMine[]): MineRoster["counts"] {
  return {
    total: mines.length,
    underground: mines.filter((mine) => mine.mine_type === "underground").length,
    opencast: mines.filter((mine) => mine.mine_type === "opencast").length,
    maharashtra: mines.filter((mine) => mine.state === "MH").length,
    madhya_pradesh: mines.filter((mine) => mine.state === "MP").length,
  };
}

/** The live roster: ten point queries run together, each allowed to fail on its own. */
export async function fetchMineRoster(signal?: AbortSignal): Promise<MineRoster> {
  const wire = await fetchMines(signal);
  const scored = await Promise.all(wire.mines.map((mine) => scoreMine(mine, signal)));
  const modelVersion = scored.find((entry) => entry.score)?.score?.model_version ?? "unavailable";
  return MineRosterSchema.parse({
    provenance: {
      data_origin: "live",
      source: "GET /mines for the cited coordinates; POST /predict/point (mask=none) at each one",
      model_version: modelVersion,
      generated_at: new Date().toISOString(),
    },
    counts: countsOf(wire.mines),
    mines: wire.mines.map((mine, index) => adaptMine(mine, scored[index]!)),
  });
}

/** The roster without scores, for a build with no backend. The mines and their
 * cited coordinates are real reference data; no score is invented for them. */
export function fixtureRoster(mines: readonly WireMine[], generatedAt: string): MineRoster {
  return MineRosterSchema.parse({
    provenance: {
      data_origin: "fixture",
      source: "Reference snapshot of GET /mines; scores need the live model",
      model_version: "unscored",
      generated_at: generatedAt,
    },
    counts: countsOf(mines),
    mines: mines.map((mine) => adaptMine(mine, null)),
  });
}

export const mineLocations = (mines: readonly WireMine[]): MineLocation[] =>
  mines.map((mine) => MineLocationSchema.parse({
    name: mine.mine_name,
    mine_type: mine.mine_type,
    location: { longitude: mine.lon, latitude: mine.lat },
  }));
