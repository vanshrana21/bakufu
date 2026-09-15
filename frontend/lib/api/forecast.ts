/** Adapters for GET /forecast and GET /production/history.
 *
 * Why explicit field-picking rather than relaxing the schema to .passthrough():
 * the two contracts disagree on field NAMES (`predicted_tonnes` vs
 * `point_estimate`), not just on extra keys. Passthrough would let the extras in
 * and still fail on the missing required fields, while silently disabling the
 * `.strict()` check that catches an adapter which forgot to map something.
 */

import type { ForecastResponse } from "@/lib/contracts";
import { ForecastResponseSchema } from "@/lib/contracts";
import type { HistoricalPoint } from "@/components/operations/production-chart";
import type { WireForecast, WireProductionHistory } from "./wire";
import {
  ContractMismatchError, apiGet, addMonths, monthToIso, toIsoTimestamp,
} from "./client";

export type ForecastHorizon = 1 | 3 | 6 | 12;

/** Every limitation below is derived from a real backtest number the backend
 * returns. None is invented: `limitations` is a required non-empty array in the
 * frontend contract, and the honest way to fill it is from measured metadata. */
function limitationsFrom(accuracy: WireForecast["accuracy_at_horizon"], model: WireForecast["model"]): string[] {
  const notes: string[] = [];
  if (accuracy) {
    if (accuracy.ci80_coverage < 80) {
      notes.push(`Interval coverage measured at ${accuracy.ci80_coverage.toFixed(1)}% against a nominal 80%: intervals are known to be too narrow.`);
    }
    if (accuracy.skill_vs_naive_pp < 0) {
      notes.push(`At this horizon the model loses to a seasonal-naive benchmark by ${Math.abs(accuracy.skill_vs_naive_pp).toFixed(2)} pp MAPE.`);
    }
    notes.push(`Backtested over ${accuracy.n_origins} rolling origins; MAPE ${accuracy.mape.toFixed(2)}%.`);
  }
  notes.push(`Company-wide aggregate from ${model.version}; no per-mine allocation is produced.`);
  return notes;
}

/** `data_cutoff` has no backend field. `model.trained_through` is the honest
 * source: it is the last month that entered the fit. */
function cutoffFrom(model: WireForecast["model"], fallback: string): string {
  try { return monthToIso(addMonths(model.trained_through, 1)); } catch { return fallback; }
}

export function adaptForecast(wire: WireForecast, lastObservedMonth: string): ForecastResponse {
  const horizon = wire.horizon_months;
  if (horizon !== 1 && horizon !== 3 && horizon !== 6 && horizon !== 12) {
    throw new ContractMismatchError("/forecast", `horizon_months ${horizon} is not one of 1, 3, 6, 12`);
  }

  // The frontend contract requires one point per month of the horizon, starting
  // at last_observed + 1 and strictly consecutive. Older backends return ONLY
  // the terminal point, which cannot be expanded without inventing the months
  // in between — so this refuses rather than fabricating a series.
  const rows = wire.series ?? (horizon === 1
    ? [{
        month: wire.target_period,
        p10: wire.predicted_lower_ci,
        p50: wire.predicted_tonnes,
        p90: wire.predicted_upper_ci,
      }]
    : null);

  if (rows === null) {
    throw new ContractMismatchError("/forecast",
      `backend returned a single terminal point for horizon=${horizon} and no "series" array. ` +
      `The chart needs ${horizon} consecutive monthly points and they cannot be interpolated. ` +
      `Requires backend contract v1.7 (adds "series"), or call with horizon=1.`);
  }
  if (rows.length !== horizon) {
    throw new ContractMismatchError("/forecast", `series has ${rows.length} points but horizon_months is ${horizon}`);
  }

  const expectedFirst = addMonths(lastObservedMonth, 1);
  if (rows[0]!.month !== expectedFirst) {
    throw new ContractMismatchError("/forecast",
      `series starts at ${rows[0]!.month} but the last observed month is ${lastObservedMonth}, ` +
      `so the first forecast month must be ${expectedFirst}`);
  }

  const issuedAt = toIsoTimestamp(wire.forecast_date);
  return ForecastResponseSchema.parse({
    forecast_id: `${wire.model.version}:${wire.forecast_date}:h${horizon}`,
    provenance: {
      data_origin: "live",
      source: `IBM MSMP monthly bulletins via ${wire.model.version} (${wire.model.variant} variant), trained through ${wire.model.trained_through}`,
      model_version: wire.model.version,
      generated_at: issuedAt,
    },
    scope: "MOIL_company_wide",
    unit: "tonnes",
    issue_date: issuedAt,
    data_cutoff: cutoffFrom(wire.model, issuedAt),
    last_observed_month: lastObservedMonth,
    horizon_months: horizon,
    interval: {
      level: wire.ci_level,
      kind: "prediction",
      method: `Prophet MCMC posterior, ${wire.model.mcmc_samples} samples, changepoint_prior_scale ${wire.model.changepoint_prior_scale}`,
    },
    points: rows.map((row) => ({
      month: row.month,
      point_estimate: row.p50,
      lower_bound: row.p10,
      upper_bound: row.p90,
    })),
  });
}

/** `limitations` belongs to the risk contract, not the forecast one, but it is
 * derived from forecast accuracy — exported so the shortfall adapter can reuse it. */
export const forecastLimitations = limitationsFrom;

export function adaptProductionHistory(wire: WireProductionHistory): {
  history: HistoricalPoint[];
  lastObservedMonth: string;
  coverage: WireProductionHistory["coverage"];
  ocrMonths: string[];
} {
  const rows = [...wire.series].sort((a, b) => a.report_month.localeCompare(b.report_month));
  if (rows.length === 0) throw new ContractMismatchError("/production/history", "series is empty; no observed month to anchor the forecast to");
  return {
    history: rows.map((row) => ({ month: row.report_month, tonnes: row.mh_plus_mp_qty_tonnes })),
    lastObservedMonth: rows[rows.length - 1]!.report_month,
    coverage: wire.coverage,
    ocrMonths: rows.filter((row) => row.extraction_method === "ocr").map((row) => row.report_month),
  };
}

// --- fetchers -------------------------------------------------------------

export const fetchProductionHistory = (options?: { start?: string; end?: string; signal?: AbortSignal }) =>
  apiGet<WireProductionHistory>("/production/history", {
    query: { start: options?.start, end: options?.end },
    signal: options?.signal,
  }).then(adaptProductionHistory);

export const fetchForecast = (horizon: ForecastHorizon, lastObservedMonth: string, signal?: AbortSignal) =>
  apiGet<WireForecast>("/forecast", { query: { horizon }, signal }).then((wire) => ({
    forecast: adaptForecast(wire, lastObservedMonth),
    accuracy: wire.accuracy_at_horizon,
    model: wire.model,
  }));
