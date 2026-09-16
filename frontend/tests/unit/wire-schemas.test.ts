import { describe, expect, it } from "vitest";
import {
  WireContractError,
  WireDashboardSummarySchema,
  WireForecastSchema,
  WireHeatmapSchema,
  WirePredictPointSchema,
  parseWire,
} from "@/lib/api/wire-schemas";

/** The boundary these schemas defend: a backend that renamed or dropped a field
 * used to arrive as `undefined`, become `NaN` inside an adapter, and surface as
 * a confusing contract error about the transformed object — or render as a
 * plausible number. It has to fail here instead, naming the field. */

const forecast = {
  forecast_date: "2026-09-09",
  target_period: "2026-10",
  horizon_months: 1,
  predicted_tonnes: 201284,
  predicted_lower_ci: 180000,
  predicted_upper_ci: 220000,
  ci_level: 0.8,
  components: { trend: 1.2 },
  model: {
    version: "prophet_baseline_v1.0",
    variant: "vanilla",
    regressors: [],
    trained_through: "2026-05",
    changepoint_prior_scale: 0.05,
    mcmc_samples: 300,
  },
  accuracy_at_horizon: null,
};

const heatmap = {
  bbox: [79, 21.3, 80.6, 22.1],
  grid: { n_cols: 2, n_rows: 2, cell_width_deg: 0.8, cell_height_deg: 0.4, origin: "top_left" },
  scores: [[0.5, null], [0.1, 0.2]],
  cells: { cells_total: 4, cells_outside_raster: 1, cells_masked_out: 0, cells_scored: 3 },
  score_range: { min: 0.1, max: 0.5, cap: 0.99 },
  mask_applied: "none",
  model_version: "prospectivity_v6",
  generated_at: "2026-09-16T10:00:00",
  cached: false,
};

const prediction = {
  prospectivity_score: 0.84,
  predicted_type: "SEDIMENTARY",
  uncertainty: 0.2,
  features_extracted: { b11: 0.4, dem: null },
  shap_top5: [{ feature: "b11", shap_value: 0.3, actual_value: null }],
  shap_base_value: null,
  model_version: "prospectivity_v6",
  lat: 21.7,
  lon: 79.8,
  prediction_id: null,
  mask_applied: "both",
  mask_decision: "masked_out_not_in_buffer",
  raw_score: 0.84,
  final_score: 0,
};

describe("wire payload validation", () => {
  it("accepts the payloads the backend actually sends", () => {
    expect(parseWire(WireForecastSchema, forecast, "/forecast").predicted_tonnes).toBe(201284);
    expect(parseWire(WireHeatmapSchema, heatmap, "/prospectivity/heatmap").scores[0]![1]).toBeNull();
    // A null SHAP value is data, not a failure: the raster had no value there.
    expect(parseWire(WirePredictPointSchema, prediction, "/predict/point").shap_top5[0]!.actual_value).toBeNull();
  });

  it("keeps passing when the backend adds a field", () => {
    const withExtra = { ...forecast, something_new: { nested: true } };
    expect(() => parseWire(WireForecastSchema, withExtra, "/forecast")).not.toThrow();
  });

  it("names the endpoint and the field when one is renamed", () => {
    const { predicted_tonnes, ...renamed } = forecast;
    const broken = { ...renamed, predicted_quantity: predicted_tonnes };
    try {
      parseWire(WireForecastSchema, broken, "/forecast");
      throw new Error("expected the parse to fail");
    } catch (error) {
      expect(error).toBeInstanceOf(WireContractError);
      expect((error as WireContractError).endpoint).toBe("/forecast");
      expect((error as Error).message).toContain("predicted_tonnes");
    }
  });

  it("refuses a number that arrived as a string, rather than passing NaN on", () => {
    expect(() => parseWire(WireHeatmapSchema, { ...heatmap, score_range: { min: "0.1", max: 0.5, cap: 0.99 } }, "/prospectivity/heatmap"))
      .toThrow(WireContractError);
  });

  it("refuses NaN and Infinity, which JSON.parse will happily produce", () => {
    expect(() => parseWire(WireForecastSchema, { ...forecast, predicted_tonnes: Number.NaN }, "/forecast"))
      .toThrow(WireContractError);
    expect(() => parseWire(WireForecastSchema, { ...forecast, ci_level: Number.POSITIVE_INFINITY }, "/forecast"))
      .toThrow(WireContractError);
  });

  it("keeps null distinct from missing on the heatmap grid", () => {
    // null means NO DATA; a missing cell means the grid itself is malformed.
    expect(() => parseWire(WireHeatmapSchema, { ...heatmap, scores: [[0.5, undefined], [0.1, 0.2]] }, "/prospectivity/heatmap"))
      .toThrow(WireContractError);
  });

  it("checks the provenance object the dashboard label depends on", () => {
    const summary = {
      generated_at: "2026-09-16T10:00:00",
      latest_actual: { month: "2026-05", mh_plus_mp_tonnes: 214624, all_india_tonnes: 300000 },
      next_forecast: { month: "2026-06", predicted_tonnes: 201284, lower_ci: 1, upper_ci: 2, ci_level: 0.8 },
      shortfall: { month: "2026-06", probability: 0.3, risk_level: "low" },
      series_health: { months_present: 123, months_missing: 0, date_range: { start: "2016-01", end: "2026-05" }, ocr_recovered_months: 2 },
      model_health: { forecast_version: "v1", shortfall_version: "v1", best_horizon: null },
      mines: { total: 11, underground: 6, opencast: 3 },
      degraded: [],
      data_provenance: { origin: "shipped trained models", synthetic: false, note: null },
    };
    expect(parseWire(WireDashboardSummarySchema, summary, "/dashboard/summary").data_provenance?.synthetic).toBe(false);
    // A provenance block that lies about its own shape is refused.
    expect(() => parseWire(WireDashboardSummarySchema, { ...summary, data_provenance: { origin: "x", synthetic: "no" } }, "/dashboard/summary"))
      .toThrow(WireContractError);
  });
});
