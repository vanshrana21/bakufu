/** Adapter for GET /mines, scored through POST /predict/point.
 *
 * Pattern matched from lib/api/forecast.ts and lib/api/predictions.ts: raw
 * backend shapes stay in wire.ts, the schema the UI renders from lives in
 * lib/contracts.ts, and this module maps between the two. A response that
 * cannot be mapped raises ContractMismatchError rather than being padded.
 *
 * The roster and the scores come from two different endpoints: /mines carries
 * the cited coordinate and its confidence, /predict/point carries the model's
 * read of that coordinate. They are fetched together so a card cannot show a
 * score without the provenance of the point it was taken at.
 */

import type { MineLocation, MineRoster } from "@/lib/contracts";
import { MineLocationSchema, MineRosterSchema } from "@/lib/contracts";
import { z } from "zod";
import type { WireMines, WirePredictPoint } from "./wire";
import { ApiRequestError, PREDICT_POINT_TIMEOUT_MS, apiGet, apiPost } from "./client";

/** Per-mine caveats, each stating a measured fact rather than a reassurance.
 *
 * Sitapatore is NOT MOIL's only opencast mine - the reference data records
 * three (Tirodi, Dongri Buzurg, Sitapatore) - and the training positives are
 * boreholes, NGDR occurrences and foreign analogues rather than underground
 * mines, so neither claim is made here. Figures come from
 * docs/mine_score_distribution_analysis.md.
 */
const CAVEATS: Record<string, string> = {
  Balaghat:
    "Deep underground workings. Satellite imagery reads surface reflectance and terrain, not ore at depth. Point scores are unstable at this resolution: ±2 km around this coordinate spans 0.02–0.99. The three nearest training occurrences, 1.5–5.1 km away, all score at the cap, so the model identifies the block rather than the shaft. Read the heatmap cell, not the point.",
  "Dongri Buzurg":
    "An opencast mine on a low score. Its coordinate is a railway-station proxy, 1–2 km from the workings, so the scored pixel may not be the pit. Elevation argues for prospectivity here (+1.27) while surface reflectance argues against it.",
  Sitapatore:
    "The lowest score of the ten, at a coordinate 3.1 km from the nearest training occurrence. The surface at this point does not match the productive pattern the model learned. Its coordinate comes from a MOIL Mining Plan rather than a boundary survey.",
};

/** The backend sends only the top five contributions by magnitude, so a point
 * may not have three in each direction. Whatever arrives is what is shown. */
const label = (feature: string) => feature.replaceAll("_", " ");

async function scoreMine(
  lat: number,
  lon: number,
  signal?: AbortSignal,
): Promise<{ score: WirePredictPoint | null; error: string | null }> {
  try {
    const wire = await apiPost<WirePredictPoint>(
      "/predict/point",
      { lat, lon },
      { signal, query: { mask: "none" }, timeoutMs: PREDICT_POINT_TIMEOUT_MS },
    );
    return { score: wire, error: null };
  } catch (error) {
    // 404 no_imagery_at_location is the backend's honest "no pixels here",
    // not a fault: it must reach the card as a stated absence, never as a zero.
    if (error instanceof ApiRequestError) {
      return { score: null, error: error.message };
    }
    throw error;
  }
}

export function adaptMineRoster(
  wire: WireMines,
  scored: ReadonlyArray<{ score: WirePredictPoint | null; error: string | null }>,
): MineRoster {
  const mines = wire.mines.map((mine, index) => {
    const result = scored[index]!;
    return {
      name: mine.mine_name,
      state: mine.state,
      district: mine.district,
      mine_type: mine.mine_type,
      location: { longitude: mine.lon, latitude: mine.lat },
      coordinate_confidence: mine.confidence,
      coordinate_source: mine.source,
      coordinate_source_url: mine.source_url,
      coordinate_precision: mine.coordinate_precision,
      coordinate_note: mine.coordinate_note,
      score: result.score
        ? {
            value: result.score.final_score ?? result.score.prospectivity_score,
            model_version: result.score.model_version,
            drivers: result.score.shap_top5.map((row) => ({
              feature: row.feature,
              label: label(row.feature),
              contribution: row.shap_value,
              observed: row.actual_value,
            })),
          }
        : null,
      score_error: result.score ? null : (result.error ?? "No score returned."),
      caveat: CAVEATS[mine.mine_name] ?? null,
    };
  });

  const modelVersion =
    scored.find((entry) => entry.score !== null)?.score?.model_version ?? "unavailable";

  return MineRosterSchema.parse({
    provenance: {
      data_origin: "live",
      source: `GET /mines for the cited coordinates; each score is a POST /predict/point at that coordinate with mask=none.`,
      model_version: modelVersion,
      generated_at: new Date().toISOString(),
    },
    mines,
    counts: {
      total: wire.counts.total,
      underground: wire.counts.underground,
      opencast: wire.counts.opencast,
    },
  });
}

/** Positions only, for the map. No scoring: see MineLocationSchema. */
export async function fetchMineLocations(signal?: AbortSignal): Promise<MineLocation[]> {
  const wire = await apiGet<WireMines>("/mines", { signal });
  return z.array(MineLocationSchema).parse(
    wire.mines.map((mine) => ({
      name: mine.mine_name,
      state: mine.state,
      district: mine.district,
      mine_type: mine.mine_type,
      location: { longitude: mine.lon, latitude: mine.lat },
      coordinate_confidence: mine.confidence,
      coordinate_source: mine.source,
      coordinate_source_url: mine.source_url,
      coordinate_note: mine.coordinate_note,
    })),
  );
}

/** Roster plus one score per mine. The scores are requested in parallel: ten
 * sequential calls would serialise ten model invocations behind one another. */
export async function fetchMineRoster(signal?: AbortSignal): Promise<MineRoster> {
  const wire = await apiGet<WireMines>("/mines", { signal });
  const scored = await Promise.all(
    wire.mines.map((mine) => scoreMine(mine.lat, mine.lon, signal)),
  );
  return adaptMineRoster(wire, scored);
}
