/** Page-level loaders. One call per view, used from Server Components.
 *
 * Each returns a LoadResult so a failed fetch renders a banner instead of
 * throwing into error.tsx and blanking a whole page. Every loader obeys the
 * same rule: in live mode a failure is an ERROR, never a quiet slide back to
 * fixtures. The `origin` field is what the UI labels the surface with.
 */

import type { ForecastResponse, RiskResponse } from "@/lib/contracts";
import type { HistoricalPoint } from "@/components/operations/production-chart";
import {
  actionFixture, forecastFixture, historyFixture, reviewRegisterFixture, riskFixture, vitalSignsFixture,
} from "@/fixtures/operations";
import { ContractMismatchError, LIVE_MODE, failedResult, fixtureResult, liveResult, type LoadResult } from "./client";
import { fetchForecast, fetchProductionHistory, type ForecastHorizon } from "./forecast";
import { fetchShortfallRisk } from "./shortfall";
import { fetchRecommendations, type RegisterRow } from "./recommendations";
import { fetchDashboardSummary, type DashboardResult, type VitalSign } from "./dashboard";

export type { RegisterRow, VitalSign, DashboardResult };

const tonnes = (value: number) => new Intl.NumberFormat("en-IN").format(Math.round(value));

/** The fixture equivalent of the dashboard tiles, derived from the same fixture
 * the register renders so the "pending reviews" count cannot disagree with it. */
function fixtureSigns(): VitalSign[] {
  const risk = vitalSignsFixture.downside_risk;
  const next = vitalSignsFixture.next_forecast;
  return [
    { label: "Latest production", value: tonnes(vitalSignsFixture.latest_production.tonnes), unit: "t",
      note: "August 2026 · synthetic observation", unavailable: false },
    { label: "Next-month forecast", value: tonnes(next.point_estimate), unit: "t",
      note: next.lower_bound !== null && next.upper_bound !== null
        ? `September · ${Math.round((forecastFixture.interval?.level ?? 0.8) * 100)}% bounds ${tonnes(next.lower_bound)}–${tonnes(next.upper_bound)} t · illustrative`
        : "September · bounds unavailable · illustrative",
      unavailable: false },
    { label: "Downside risk",
      value: risk.value_type === "probability" ? `${Math.round(risk.probability * 100)}%` : String(risk.score.value),
      unit: null, note: "Below 90% of issued forecast · unvalidated", testId: "vital-risk", unavailable: false },
    { label: "Pending reviews", value: String(vitalSignsFixture.pending_reviews).padStart(2, "0"),
      unit: "awaiting review", note: "Proposed actions · no approvals recorded", unavailable: false },
  ];
}

export interface ForecastBundle {
  forecast: ForecastResponse;
  /** Null when the shortfall model is degraded. The forecast is still valid on
   * its own, so one failed component must not blank the other — the backend's
   * /dashboard/summary degrades the same way. */
  risk: RiskResponse | null;
  riskError: string | null;
  history: readonly HistoricalPoint[];
  /** Set when the requested horizon could not be served as a series and the
   * loader fell back to a single month. The panel shows it so a one-point
   * chart is never mistaken for a three-month outlook. */
  horizonNote: string | null;
}

/** Forecast + risk + history together: the risk carries `reference_forecast_id`,
 * and ForecastRiskPanel refuses to co-render a risk that references a different
 * forecast. Fetching them separately would let that pairing drift. */
export async function loadForecastBundle(horizon: ForecastHorizon = 3): Promise<LoadResult<ForecastBundle>> {
  if (!LIVE_MODE) {
    return fixtureResult({ forecast: forecastFixture, risk: riskFixture, riskError: null, history: historyFixture, horizonNote: null });
  }
  try {
    const production = await fetchProductionHistory();

    // The backend currently returns only the TERMINAL point for a multi-month
    // horizon - no `series[]` - and the missing months cannot be interpolated.
    // Rather than blanking the whole panel, fall back to the one month it can
    // serve honestly and label the chart accordingly. Remove this once
    // GET /forecast ships a series array.
    let forecast: ForecastResponse;
    let horizonNote: string | null = null;
    try {
      forecast = (await fetchForecast(horizon, production.lastObservedMonth)).forecast;
    } catch (error) {
      if (!(error instanceof ContractMismatchError) || horizon === 1) throw error;
      forecast = (await fetchForecast(1, production.lastObservedMonth)).forecast;
      horizonNote =
        `Showing 1 month, not ${horizon}: GET /forecast returns only the final month of a ` +
        `multi-month horizon and the intermediate months cannot be derived. ` +
        `The single point shown is real model output.`;
    }
    // Shortfall is fetched separately and allowed to fail: three of the
    // classifier's nine features are rainfall terms read from Postgres, so it
    // degrades independently of the forecast whenever DATABASE_URL is unset.
    let risk: RiskResponse | null = null;
    let riskError: string | null = null;
    try {
      risk = (await fetchShortfallRisk(forecast.forecast_id)).risk;
    } catch (error) {
      riskError = failedResult<RiskResponse>(error).error;
    }
    // Keep the chart readable: the full MSMP series is 123 months.
    const history = production.history.slice(-18);
    return liveResult({ forecast, risk, riskError, history, horizonNote });
  } catch (error) {
    return failedResult<ForecastBundle>(error);
  }
}

export async function loadRegister(): Promise<LoadResult<{ rows: RegisterRow[]; message: string | null; footnotes: string[] }>> {
  if (!LIVE_MODE) {
    return fixtureResult({ rows: reviewRegisterFixture.map((row) => ({ ...row })), message: null, footnotes: [] });
  }
  try {
    const production = await fetchProductionHistory();
    // horizon=1 on purpose: the register only needs a forecast id to link the
    // risk against, and horizon=1 is the one shape every backend version serves.
    const { forecast } = await fetchForecast(1, production.lastObservedMonth);
    const { risk, raw } = await fetchShortfallRisk(forecast.forecast_id);
    const result = await fetchRecommendations({
      linkedRiskId: risk.risk_id,
      modelVersion: raw.model_metadata.version,
      limit: 20,
    });
    return liveResult({ rows: result.rows, message: result.message, footnotes: result.footnotes });
  } catch (error) {
    return failedResult(error);
  }
}

export async function loadDashboard(): Promise<LoadResult<DashboardResult>> {
  if (!LIVE_MODE) {
    return fixtureResult({
      signs: fixtureSigns(), degraded: [], syntheticNote: null,
      generatedAt: actionFixture.provenance.generated_at,
      seriesHealth: null, modelHealth: { forecast_version: "mock-only", shortfall_version: "mock-only", best_horizon: null },
    });
  }
  try {
    const register = await loadRegister();
    const pending = register.data ? register.data.rows.filter((row) => row.action.review_status === "proposed").length : null;
    return liveResult(await fetchDashboardSummary(pending));
  } catch (error) {
    return failedResult<DashboardResult>(error);
  }
}
