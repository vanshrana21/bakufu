# Phase 4 API Contracts — v1.6

Source of truth for the frontend. Schemas here are fixed; if implementation
forces a change, the change is raised before it is made, not after.

**v1.6 changes from v1.5:** `/recommendations` is implemented — the `501`
stub is gone. Adds `context.footnotes`, `coverage_complete`,
`action_types_included` / `action_types_omitted`, and a new
`GET /recommendations/scenario/{month}`.

**v1.5 changes from v1.4:** clarified that `/dashboard/summary`'s `degraded`
field is always present. Documentation only - no behaviour change.

**v1.4 changes from v1.3:** heatmap cold SLA relaxed 30 s -> 45 s to match
measured 38 s; warming documented as asynchronous; API version 0.2.

**v1.3 changes from v1.2:** corrected `counts.with_generic_fleet_only` from
3 to 4 — Dongri Buzurg was missing from the count — and added it to the
`is_generic_fallback` list. Value change only, no shape change.

**v1.2 changes from v1.1:** four-state cell rendering guide on
`/prospectivity/heatmap`; three warm viewports named from
`settings.HEATMAP_WARM_VIEWPORTS`; prospectivity model promoted v1 -> v6, so
`model_version` now reads `prospectivity_v6`.

**v1.1 changes from v1.0:** `coverage` scoping note on `/production/history`;
`top_features` renamed to `feature_contributions` and now returns all nine;
`feature_provenance` keyed by concern; `/mines` counts gained
`with_capacity_target` and `with_generic_fleet_only`; new
`GET /prospectivity/heatmap` (section 10).

Base URL (local dev): `http://127.0.0.1:8000`

## Conventions

**Validation errors are always `422`**, using FastAPI's native error body. There
is no `400`: a well-formed request carrying invalid contents is Unprocessable
Entity, and one shape means the frontend needs one handler.

```json
{
  "detail": [
    {
      "type": "value_error",
      "loc": ["query", "horizon"],
      "msg": "horizon must be one of 1, 3, 6, 12",
      "input": "7"
    }
  ]
}
```

**Server-side failures return `500`** with a flat body carrying a machine
-readable code:

```json
{
  "error_code": "model_not_loaded",
  "detail": "prophet_baseline_v1_0_shipped.pkl not found in models/",
  "remedy": "run python -m src.models.forecast.prophet_baseline --variant vanilla, then promote the artifact"
}
```

Error codes: `model_not_loaded`, `data_not_loaded`, `prediction_failed`.

**An empty result is `200`, never an error.** A date filter matching no months
returns `series: []` with `coverage.months_present: 0`.

**Months are `YYYY-MM` strings** throughout. Tonnages are floats in tonnes.

**Authentication is optional.** When the server sets `API_KEY`, every route
except `GET /` requires that value in the `X-API-Key` header. A missing or wrong
key is `401` with the usual flat body:
`{"error_code": "unauthorized", "detail": "missing or invalid API key", "remedy": "..."}`.

### Model path split

Endpoints read frozen, promoted artifacts. Training writes elsewhere, and
promotion is a manual copy. This exists because the 3.2c rainfall run
overwrote `prophet_baseline_v1.pkl` and the API silently served the rejected
variant while returning `200`.

| purpose | path |
|---|---|
| served forecast model | `models/prophet_baseline_v1_0_shipped.pkl` |
| served forecast metrics | `data/processed/prophet_metrics_baseline_v1_0.json` |
| served backtest rows | `data/processed/prophet_backtest_rows_baseline_v1_0.parquet` |
| served shortfall model | `models/shortfall_classifier_v1.pkl` |
| training scratch (never served) | `models/prophet_baseline_v1.pkl` |

Models load once in the FastAPI lifespan handler and live in `app.state`.

---

## 1. `GET /production/history`

Monthly MH+MP manganese production from the IBM MSMP bulletins.

**Query params**

| name | type | default | rules |
|---|---|---|---|
| `start` | string `YYYY-MM` | `null` (series start) | must parse as a month; `422` otherwise |
| `end` | string `YYYY-MM` | `null` (series end) | must parse; must be `>= start` or `422` |

**Response `200`**

```json
{
  "series": [
    {
      "report_month": "2026-05",
      "mh_qty_tonnes": 106289.75,
      "mp_qty_tonnes": 108334.53,
      "mh_plus_mp_qty_tonnes": 214624.28,
      "all_india_qty_tonnes": 439949.424,
      "extraction_method": "text"
    }
  ],
  "coverage": {
    "months_present": 123,
    "months_missing": 2,
    "date_range": {"start": "2016-01", "end": "2026-05"},
    "gaps": ["2016-03", "2023-03"]
  },
  "metadata": {
    "source": "IBM MSMP monthly bulletins",
    "proxy_note": "MH+MP is used as proxy for MOIL operating region (~49% of India's manganese)"
  }
}
```

`extraction_method` is `"text"` or `"ocr"`. Five months are `"ocr"`
(2020-07, 2024-09, 2025-02, 2025-05, 2025-10); the frontend may badge them.

> **Note:** `coverage` is scoped to the query window. `months_missing`,
> `date_range`, and `gaps` all describe the filtered response, not the
> underlying series. To get global series health, call with no params.

```bash
curl "http://127.0.0.1:8000/production/history?start=2024-01&end=2026-05"
```

---

## 2. `GET /mines`

The ten MOIL operating mines.

**Query params**

| name | type | default | rules |
|---|---|---|---|
| `state` | string | `null` | `MH` or `MP`; anything else `422` |
| `mine_type` | string | `null` | `underground`, `opencast`, `mixed`; else `422` |

**Response `200`**

```json
{
  "mines": [
    {
      "mine_name": "Balaghat",
      "state": "MP",
      "district": "Balaghat",
      "mine_type": "underground",
      "equipment": ["SDL", "rocker_shovel", "shaft_sinking_rig"],
      "capacity_target_tonnes": 800000,
      "notes": "Company's largest mine; described as the deepest underground manganese mine in Asia...",
      "sources": [
        {"tag": "IBM_2022", "url": "https://ibm.gov.in/writereaddata/files/17125770456613da1576db0Manganese_Ore_2022.pdf"}
      ],
      "type_note": null
    }
  ],
  "counts": {
    "total": 10, "underground": 7, "opencast": 3, "mixed": 0,
    "MH": 6, "MP": 4,
    "with_capacity_target": 3,
    "with_generic_fleet_only": 4
  }
}
```

`capacity_target_tonnes` is `null` for seven of ten mines — only Balaghat
(800000), Gumgaon (350000) and Kandri (100000) disclose a numeric target.
`type_note` is non-null **only for Kandri**; the frontend should treat it as
optional and render it as a tooltip where present.

Districts for the six Maharashtra mines are inferred from general geography,
not source-cited — do not present them as sourced facts.

```bash
curl "http://127.0.0.1:8000/mines?state=MP"
```

---

## 3. `GET /mines/{mine_name}`

**Path param:** `mine_name`, case-sensitive, must match a key exactly
(`Balaghat`, `Ukwa`, `Sitapatore`, `Tirodi`, `Gumgaon`, `Kandri`, `Munsar`,
`Beldongri`, `Chikla`, `Dongri Buzurg`). URL-encode the space in
`Dongri%20Buzurg`.

**Response `200`** — a single mine object as above, plus the fleet vocabulary
so the frontend can render generic fallbacks:

```json
{
  "mine_name": "Kandri",
  "state": "MH",
  "district": "Nagpur",
  "mine_type": "underground",
  "type_note": "Company classification underground; EC summary suggests mixed opencast/underground component",
  "equipment": ["dumper_20_to_25t", "water_tanker_sprinkler", "hydraulic_sand_stowing", "shaft_sinking_rig"],
  "capacity_target_tonnes": 100000,
  "notes": "Expansion proposal 0.063 MTPA to 0.100 MTPA...",
  "sources": [
    {"tag": "IBM_2020", "url": "https://ibm.gov.in/writereaddata/files/04272022163406Manganese_2020.pdf"},
    {"tag": "MPCB_KANDRI_EC", "url": "https://mpcb.ecmpcb.in/notices/pdf/kandri.pdf"}
  ],
  "fleet_vocabulary": {
    "applicable": ["SDL", "rocker_shovel", "electro_hydrostatic_drill", "hydraulic_sand_stowing", "shaft_sinking_rig", "rock_mechanics_monitoring"],
    "is_generic_fallback": false
  }
}
```

`is_generic_fallback` is `true` for the four mines whose `equipment` is a
placeholder (`Munsar`, `Beldongri`, `Sitapatore`, `Dongri Buzurg`),
signalling that no mine-specific fleet was disclosed with sufficient detail.

> **Dongri Buzurg footnote:** its source mentions equipment (excavator,
> dumper) but gives no capacity. Following the same source-caution as the
> other generic-fleet mines, we do not tag a specific dumper capacity we
> cannot verify.

**`404`** for an unknown mine:

```json
{"detail": "mine 'Foo' not found. Known mines: Balaghat, Beldongri, Chikla, ..."}
```

```bash
curl "http://127.0.0.1:8000/mines/Dongri%20Buzurg"
```

---

## 4. `GET /forecast`

Prophet forecast of MH+MP production.

**Query params**

| name | type | default | rules |
|---|---|---|---|
| `horizon` | int | `1` | one of `1, 3, 6, 12`; else `422` |

**Response `200`**

```json
{
  "forecast_date": "2026-09-09",
  "target_period": "2026-06",
  "horizon_months": 1,
  "predicted_tonnes": 201283.82,
  "predicted_lower_ci": 176_000.0,
  "predicted_upper_ci": 226_000.0,
  "ci_level": 0.80,
  "components": {"trend": 198500.0, "yearly": 0.014, "multiplicative_terms": 0.014},
  "model": {
    "version": "prophet_baseline_v1.0",
    "variant": "vanilla",
    "regressors": [],
    "trained_through": "2026-05",
    "changepoint_prior_scale": 0.25,
    "mcmc_samples": 300
  },
  "accuracy_at_horizon": {
    "mape": 10.93,
    "naive_mape": 9.67,
    "skill_vs_naive_pp": -1.26,
    "ci80_coverage": 64.0,
    "n_origins": 25
  },
  "series": [
    {"month": "2026-06", "month_label": "Jun 2026", "p10": 176543.21, "p50": 201283.82, "p90": 227110.23}
  ]
}
```

`series` has one row per month of the horizon, from the first forecast month
to `target_period`, all from the same `predict()` call. `p10`/`p90` are the
bounds of the 80% interval; `p50` is Prophet's point estimate. The last row
equals the top-level `predicted_*` fields, which stay for older clients.

`components` keys vary with the fitted model; the shipped vanilla variant has
**no rainfall or capex component**, so the frontend must iterate whatever keys
arrive rather than indexing fixed names.

`accuracy_at_horizon` is the backtest row for the requested horizon, so the UI
can show honest error bars. **`skill_vs_naive_pp` is negative at horizons 1, 3
and 6** — the model loses to seasonal-naive there and only wins at 12
(`+0.24`). That is a real property of the series, and the frontend should not
present the forecast as beating a naive benchmark at short horizons.

`ci80_coverage` is 60–71%, below the nominal 80%. Intervals are known to be
too tight; recalibration is open work.

```bash
curl "http://127.0.0.1:8000/forecast?horizon=12"
```

---

## 5. `GET /forecast/history`

Backtest metrics per horizon for the shipped model.

**No query params.**

**Response `200`**

```json
{
  "horizons": [
    {"horizon_months": 1, "n_origins": 25, "mape": 10.93, "rmse": 25320.0,
     "naive_mape": 9.67, "skill_vs_naive_pp": -1.26, "ci80_coverage": 64.0},
    {"horizon_months": 12, "n_origins": 14, "mape": 9.92, "rmse": 25948.0,
     "naive_mape": 10.16, "skill_vs_naive_pp": 0.24, "ci80_coverage": 71.4}
  ],
  "origins": [
    {"horizon_months": 1, "origin_month": "2024-05", "target_month": "2024-06",
     "actual_tonnes": 150644.0, "predicted_tonnes": 158200.0, "covered": true}
  ],
  "model": {"version": "prophet_baseline_v1.0", "variant": "vanilla"},
  "benchmark": {"name": "seasonal_naive", "definition": "same calendar month one year earlier"}
}
```

`origins` is the per-origin detail (82 rows across four horizons) for plotting
actual-vs-predicted. If the frontend only needs the summary, read `horizons`.

```bash
curl "http://127.0.0.1:8000/forecast/history"
```

---

## 6. `GET /shortfall/risk`

Probability that next month's production falls below 90% of the Prophet
forecast, with a SHAP explanation.

**No query params.** The endpoint always scores the next unobserved month.

Schema below is derived from the shipped `shortfall_classifier_v1.pkl` and the
real 2026-06 prediction, not from the retired scaffold's schema.

**Response `200`**

```json
{
  "as_of": "2026-05",
  "forecast_month": "2026-06",
  "shortfall_probability": 0.1073,
  "risk_level": "low",
  "shortfall_definition": "actual production below 90% of the Prophet forecast for that month",
  "prophet_forecast_tonnes": 201283.82,
  "shortfall_threshold_tonnes": 181155.44,
  "feature_contributions": [
    {
      "feature_name": "deviation_lag1",
      "human_label": "Last month vs forecast",
      "value": 0.074,
      "display_value": "+7.4%",
      "shap_contribution": -1.5043,
      "direction": "decreases_risk"
    },
    {
      "feature_name": "prophet_forecast_level",
      "human_label": "Forecast production level",
      "value": 201283.82,
      "display_value": "201,284 t",
      "shap_contribution": -1.1578,
      "direction": "decreases_risk"
    },
    {
      "feature_name": "rainfall_lag2_mm",
      "human_label": "Rainfall 2 months ago",
      "value": 1.5,
      "display_value": "1.5 mm",
      "shap_contribution": 1.0273,
      "direction": "increases_risk"
    },
    {
      "feature_name": "production_trend_3mo",
      "human_label": "3-month production trend",
      "value": 1.117,
      "display_value": "+11.7% vs prior quarter",
      "shap_contribution": -0.4871,
      "direction": "decreases_risk"
    },
    {
      "feature_name": "rainfall_lag1_mm",
      "human_label": "Rainfall last month",
      "value": 3.968,
      "display_value": "4.0 mm",
      "shap_contribution": 0.3199,
      "direction": "increases_risk"
    }
  ],
  "shap_base_value": -0.0128,
  "feature_provenance": {
    "rainfall": "observed",
    "prophet_forecast": "shipped_model"
  },
  "model_metadata": {
    "version": "shortfall_classifier_v1",
    "base_rate": 0.217,
    "roc_auc": 0.749,
    "pr_auc": 0.344,
    "trained_on_months": 60,
    "trained_on_positives": 13,
    "decision_threshold": 0.5
  }
}
```

`feature_contributions` returns **all nine features**, sorted by
`|shap_contribution|` descending. The API does not decide how many the UI
shows - the frontend slices. Nine items is a negligible payload difference
and avoids baking a display choice into the contract. `shap_contribution`
is in log-odds; `shap_base_value + sum(all nine contributions)` passes through
a sigmoid to `shortfall_probability` exactly, so the frontend can show a
waterfall that reconciles.

`risk_level` thresholds on probability: `low < 0.25`, `medium 0.25–0.50`,
`high >= 0.50`.

`feature_provenance` is keyed by concern so it can grow without a breaking
change. `rainfall` is `"observed"` or `"imputed_climatology"`;
`prophet_forecast` is `"shipped_model"` or `"scratch_model"`. It
exists because a silent climatology fallback produced a false null in Phase
3.2c; if it ever reads `imputed_climatology`, the explanation is weaker and
the UI should say so.

**Honest-framing fields the UI should surface:** the model was trained on 60
months with 13 positives, and COVID-scale shocks are absent from that window.
It is a screening tool (precision 0.33, recall 0.71), not a prediction.

```bash
curl "http://127.0.0.1:8000/shortfall/risk"
```

---

## 7. `GET /dashboard/summary`

One call for the landing view; composes the endpoints above.

**No query params.**

**Response `200`**

```json
{
  "generated_at": "2026-09-09T14:20:00Z",
  "latest_actual": {"month": "2026-05", "mh_plus_mp_tonnes": 214624.28, "all_india_tonnes": 439949.424},
  "next_forecast": {
    "month": "2026-06", "predicted_tonnes": 201283.82,
    "lower_ci": 176000.0, "upper_ci": 226000.0, "ci_level": 0.80
  },
  "shortfall": {"month": "2026-06", "probability": 0.1073, "risk_level": "low"},
  "series_health": {
    "months_present": 123, "months_missing": 2,
    "date_range": {"start": "2016-01", "end": "2026-05"},
    "ocr_recovered_months": 5
  },
  "model_health": {
    "forecast_version": "prophet_baseline_v1.0",
    "shortfall_version": "shortfall_classifier_v1",
    "best_horizon": {"horizon_months": 12, "mape": 9.92, "skill_vs_naive_pp": 0.24}
  },
  "mines": {"total": 10, "underground": 7, "opencast": 3}
}
```

If a component fails to load, its block is `null` and the rest still returns
`200` — a broken shortfall model must not blank the whole landing page. The
key itself is always present: a missing key and a null key behave differently
in a TypeScript client.

`degraded` is always present in the response. In the happy case it's an empty
array `[]`. When component endpoints fail, it contains their names (e.g.
`["shortfall"]`). Frontends can rely on the field always being an array and
check length > 0 for degradation state.

```json
{"shortfall": null, "degraded": ["shortfall"]}
```

```bash
curl "http://127.0.0.1:8000/dashboard/summary"
```

---

## 8. `GET /recommendations`

Corrective actions derived from the live shortfall SHAP explanation. Closes
three problem-statement bullets: adjusting mine schedules, optimising blasting,
and re-deploying equipment.

The endpoint reuses the cached `/shortfall/risk` payload rather than
recomputing SHAP. There are no per-mine forecasts, so a named mine gets the
**same aggregate risk score** with its own fleet vocabulary applied; the
`mine_type` decides whether underground or opencast rules fire.

**Query params**

| name | type | default | rules |
|---|---|---|---|
| `mine_name` | string | `null` | must match a known mine; else `422` |
| `limit` | int | `5` | 1-20; else `422` |

### Behaviour by risk level

| `shortfall_probability` | behaviour |
|---|---|
| `< 0.25` (low) | empty `recommendations`, `context.message` explains why, `footnotes` empty |
| `0.25 - 0.60` (medium) | 1-2 cards from the **primary driver only**; no action-type guarantee |
| `>= 0.60` (high) | all three action types guaranteed, subject to `limit` |

Only features with **positive** SHAP - those arguing *for* a shortfall -
generate actions. Features with negative SHAP explain why the forecast is
currently healthy and warrant no intervention. Ranking by absolute SHAP would,
on the current live prediction, fire actions against recent production
performance, whose contributions are all negative because last month beat
forecast by 7.4%.

**Response `200`**

```json
{
  "generated_at": "2026-09-11T09:20:00Z",
  "context": {
    "mine_name": "Balaghat",
    "mine_type": "underground",
    "shortfall_probability": 0.9103,
    "forecast_month": "2021-04",
    "risk_level": "high",
    "drivers_ranked": [
      {"driver": "rainfall_signal", "label": "Rainfall and monsoon impact", "positive_shap": 1.5669},
      {"driver": "production_history_signal", "label": "Recent production performance", "positive_shap": 1.4412}
    ],
    "footnotes": []
  },
  "recommendations": [
    {
      "id": "ug_rain_shift_sequence",
      "action_type": "schedule_adjustment",
      "title": "Re-sequence development shifts away from wet-season faces",
      "rationale": "rainfall 2 months ago (7.1 mm) is the leading risk driver. Move development effort to levels least exposed to inflow before the next cycle is planned.",
      "equipment_referenced": ["rock_mechanics_monitoring"],
      "priority": "high",
      "driver": "rainfall_signal",
      "driver_label": "Rainfall and monsoon impact",
      "triggered_by": [
        {"signal": "rainfall_lag2_mm", "value": 7.1, "display_value": "7.1 mm", "shap_contribution": 1.0273}
      ],
      "confidence": "rule_based"
    }
  ],
  "coverage_complete": true,
  "action_types_included": ["blasting_optimization", "equipment_redeployment", "schedule_adjustment"],
  "action_types_omitted": []
}
```

`action_type` is one of `schedule_adjustment`, `blasting_optimization`,
`equipment_redeployment`.

`equipment_referenced` items come only from `UNDERGROUND_FLEET_VOCAB` or
`OPENCAST_FLEET_VOCAB`. Public sources record no LHD, jumbo drill or
100-tonne dumper at any MOIL mine, so generic mining terminology would name
equipment MOIL does not operate. A test iterates every rule template to
enforce this.

`confidence` is always `rule_based` - these are deterministic rules over model
output, not a learned score, and the UI should not imply otherwise.

### `coverage_complete` and `limit`

At `p >= 0.60` the response is guaranteed to carry one card of each action
type. `limit` **wins** over that guarantee: an explicit caller request is not
overridden. When `limit < 3` truncates the set, action-type *diversity* is
preserved rather than taking top-N by priority, so `limit=2` returns two
different action types:

```json
{"coverage_complete": false,
 "action_types_included": ["schedule_adjustment", "equipment_redeployment"],
 "action_types_omitted": ["blasting_optimization"]}
```

### `context.footnotes`

Always present, an array, usually empty. It carries an explanation only when a
contribution is **counterintuitive** - a feature whose raw value reads as good
news while its SHAP pushes risk up. Three features can do this:
`production_trend_3mo` above 1.0, and `deviation_lag1` / `deviation_lag2` above
zero. A rising trend raising shortfall risk is genuine model behaviour (mean
reversion: the forecast rises with recent output, so the next month must
sustain a higher level), but a card quoting it without explanation reads as a
non-sequitur.

Rainfall, forecast level and the seasonal terms raising risk are intuitive and
never produce a footnote. Footnotes are suppressed entirely when no cards
render, since there would be nothing for them to explain.

```bash
curl "http://127.0.0.1:8000/recommendations?mine_name=Balaghat&limit=3"
```

---

## 8b. `GET /recommendations/scenario/{month}`

Replays the classifier over a real historical month and returns the
recommendations that month's actual SHAP output produces.

The current month usually scores low risk - correctly - so `/recommendations`
returns an empty card set. This endpoint exists so a reviewer can see the
engine working on **real data and real model output**, rather than a
fabricated scenario or a `simulate_probability` parameter that would leave
demo-only code in the production surface.

**Path param:** `month`, `YYYY-MM`. Must appear in `settings.SCENARIO_MONTHS`;
otherwise `404` naming the available months.

**Query params:** `mine_name` and `limit`, exactly as section 8.

Configured months, both real shortfalls the model flags at `p >= 0.60`,
picked for different driver profiles so the taxonomy visibly switches:

| month | p | leading driver | actual shortfall |
|---|---|---|---|
| `2021-04` | 0.910 | `rainfall_signal` (1.567) | yes |
| `2024-02` | 0.991 | `forecast_level_signal` (2.247) | yes |

Months before 2021-04 are unavailable: the classifier's feature table begins
there, because the `min_train_for_label = 60` cut excluded early origins where
a young Prophet manufactured artefactual shortfalls.

**Response `200`** — identical to section 8, plus three context fields:

```json
{
  "context": {
    "scenario_month": "2021-04",
    "is_historical_replay": true,
    "actual_shortfall": true
  }
}
```

`actual_shortfall` is the recorded label for that month, so the UI can state
that the month genuinely undershot rather than implying a hypothetical.

```bash
curl "http://127.0.0.1:8000/recommendations/scenario/2021-04"
```

---

## 9. `POST /forecast/retrain`

**Demo mode: stubbed.** Returns `501`:

```json
{
  "error_code": "not_implemented",
  "detail": "retraining is disabled in demo mode",
  "remedy": "run python -m src.models.forecast.prophet_baseline locally, then promote the artifact"
}
```

Retraining takes roughly 40 minutes with MCMC sampling, cannot be
meaningfully awaited in a demo, and the previous implementation wrote to the
served model path — the exact mechanism that put the rejected rainfall variant
into production. The existing `GET /forecast/retrain/{task_id}` stays for
shape compatibility and reports `404` for unknown ids.

---

## 10. `GET /prospectivity/heatmap`

Gridded prospectivity scores for the map view.

This endpoint exists because `POST /predict/bbox` cannot feed a map: it
returns a score-sorted list whose cells do not lie on a lattice, and which
includes cells outside the requested bbox. See `docs/known_issues.md`.
Phase 2 is frozen, so this routes around it rather than fixing it.

**Query params**

| name | type | default | rules |
|---|---|---|---|
| `min_lon` | float | required | -180..180; `< max_lon` else `422` |
| `min_lat` | float | required | -90..90; `< max_lat` else `422` |
| `max_lon` | float | required | -180..180 |
| `max_lat` | float | required | -90..90 |
| `grid_size` | int | `32` | cells per side, 8..128; else `422` |
| `mask` | string | `none` | `none`, `geological`, `occurrence_buffer`, `both`; else `422` |

`mask` uses the **same vocabulary as `/predict/point` and `/predict/bbox`**
(`VALID_MASKS`), so one enum covers every prospectivity endpoint.

`grid_size` is cells per side rather than a distance, so the client controls
payload size directly. Non-square bboxes give non-square cells; the response
reports the actual `cell_width_deg` and `cell_height_deg` it used.

**Response `200`**

```json
{
  "bbox": [79.53, 21.32, 80.57, 22.05],
  "grid": {
    "n_cols": 32,
    "n_rows": 32,
    "cell_width_deg": 0.0325,
    "cell_height_deg": 0.0228,
    "origin": "top_left"
  },
  "scores": [[0.12, 0.31, null, "..."], ["..."]],
  "cells": {
    "cells_total": 1024,
    "cells_outside_raster": 118,
    "cells_masked_out": 240,
    "cells_scored": 666
  },
  "score_range": {"min": 0.001, "max": 0.99, "cap": 0.99},
  "mask_applied": "none",
  "model_version": "prospectivity_v6",
  "generated_at": "2026-09-09T14:20:00Z",
  "cached": true
}
```

`scores` is row-major, `n_rows` arrays of `n_cols` floats, aligned exactly to
the requested bbox with `origin: "top_left"` so it drops onto a Leaflet or
MapLibre image overlay without flipping.

**`null` means no data, and is distinct from `0.0`.** A cell is `null` when it
falls outside the imagery footprint **or** when every feature extracted for it
is null. The second case matters: `/predict/point` currently returns the
capped score `0.990` for such cells, so Kandri and Beldongri - both just
outside the footprint - score as maximum prospectivity on no data at all. A
heatmap that rendered those would put its two brightest hotspots where nothing
was measured. See `docs/known_issues.md`.

### Cell states — how to render each

`scores` cells take exactly four states. Conflating the first two would
misreport absence of data as absence of prospectivity.

| state | meaning | render as |
|---|---|---|
| `null` | **no data** — outside the imagery footprint, or every feature for the cell was null | transparent, or a "no data" hatch. **Never** the bottom of the colour scale. |
| `0.0` | a genuine low score, **or** a cell a mask excluded | bottom of the colour scale |
| `0.0 < s <= 0.99` | a real score | on the colour scale |
| `> 0.99` | cannot occur — scores are capped | n/a; legend maximum should read **"≥ 0.99"**, not `1.0` |

`cells_masked_out` counts cells a mask zeroed; those are returned as `0.0`,
not `null`, because "excluded by geology" is a finding, not missing data.

**Colour-ramp note:** under the promoted v6 bundle, roughly **24.5% of cells
score at or above 0.90**. A linear 0–0.99 ramp will render about a quarter of
the map at maximum intensity. A percentile-based or non-linear ramp separates
the top of the distribution far better.

`score_range.cap` surfaces the 0.99 ceiling so the legend does not imply a
true 1.0 maximum.

### Performance

**This endpoint's SLA is deliberately different from the rest of the API:
5 s warm / 45 s cold. Startup pre-warming for the three configured viewports
means the demo never hits a cold path; the cold number is documented for
completeness only.** It is not held to the 500 ms target that applies to
`/forecast` and `/shortfall/risk`, because it scores up to 16,384 cells with
per-cell feature extraction.

Caching:

- key is `(bbox rounded to 4dp, grid_size, mask, model_version)` - the model
  version is in the key so a hotfixed model cannot serve stale tiles
- persisted to `data/cache/heatmap_{hash}.json`, 24-hour TTL
- warming runs asynchronously on API startup for the viewports in
  `settings.HEATMAP_WARM_VIEWPORTS`. The API is available immediately; warming
  completes in the background (~2 minutes for three viewports) and populates
  the cache before the demo would realistically first hit it. Warming failures
  log a warning but don't block startup. The viewports are:
  `full_bbox` `[79.0, 21.3, 80.6, 22.1]`, `balaghat_bhandara`
  `[79.53, 21.32, 80.57, 22.05]`, `balaghat_ukwa` `[80.05, 21.70, 80.60, 22.05]`
  — all at `grid_size=32`, and all fully inside the usable raster footprint,
  so none contain null cells
- `cached: true` in the response tells the client it was a cache hit

```bash
curl "http://127.0.0.1:8000/prospectivity/heatmap?min_lon=79.53&min_lat=21.32&max_lon=80.57&max_lat=22.05&grid_size=32&mask=none"
```


---

## CORS

Allowed origins: `http://localhost:3000`, `http://localhost:5173`,
`http://localhost:8080`, plus `127.0.0.1` equivalents. No production origin is
configured; adding one needs an explicit decision.

## Logging

Every request logs `method`, `path`, `status`, `elapsed_ms`.

## Performance

`/forecast` and `/shortfall/risk` target < 500 ms. Models load once at startup
into `app.state`; per-request cost is prediction only. `/forecast` at
`horizon=12` builds a 12-row future frame and is the slowest path.

---
