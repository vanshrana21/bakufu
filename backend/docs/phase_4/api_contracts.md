# Phase 4 API Contracts — v1.10

Source of truth for the frontend. Schemas here are fixed; if implementation
forces a change, the change is raised before it is made, not after.

**v1.10 changes from v1.9:** `POST /predict/point` adds **`raw_probability`**
and **`model_margin`**, the classifier's own output before the Elkan-Noto
adjustment and the 0.99 cap (section 12). Additive and nullable: every existing
field is unchanged, and a client that ignores them sees v1.9 behaviour.

**v1.9 changes from v1.8:** `GET /forecast` adds **`series`**, one point per
month of the horizon, so a chart no longer has to interpolate the months
between the origin and the terminal point. Additive: every existing field is
unchanged, and the last `series` entry equals the top-level `predicted_*`
values.

**v1.8 changes from v1.7:** prospectivity scoring now reads the mosaic v6 was
trained on (`s2_moil_operational_v1.tif`, the training mosaic plus a western
strip covering Gumgaon). Scores change at most coordinates. `POST
/predict/point` returns `404` with the flat error body and `error_code:
"no_imagery_at_location"` wherever there is no real imagery; previously such
points returned a score computed from blank pixels. A heatmap cell is `null`
under the same condition.
`/mines` and `/mines/{mine_name}` add `lat`, `lon`, `confidence`, `source`,
`source_url` (null where no full URL exists), `coordinate_precision` and
`coordinate_note`; coordinates are corrected from cited sources and
Sitapatore moves to its MOIL Mining Plan point in Madhya Pradesh.

**v1.7 changes from v1.6:** `/forecast` is horizon-adaptive: seasonal-naive
serves horizons 1, 3 and 6, Prophet serves 12. It adds `model_used`, `reason`,
`model.interval_method` and `accuracy_at_horizon.prophet_mape`.
**Semantic change:** `accuracy_at_horizon` now describes the *served* model;
in v1.6 its `mape`, `rmse`, `ci80_coverage` and `skill_vs_naive_pp` were
always Prophet's. `/forecast/history` adds a per-horizon `comparison`,
per-origin `seasonal_naive_tonnes` and a top-level `routing` block.
`/dashboard/summary` `next_forecast` adds `model_used`.
`POST /predict/bbox` is renamed `POST /predict/points_in_bbox`; the old path
still answers, marked deprecated (section 11).
**v1.8 changes from v1.7:** `GET /` adds `provenance_bound`;
`/dashboard/summary`'s `data_provenance` adds `prospectivity_provenance_bound`;
`GET /predictions/{prediction_id}` adds `encoder_version`, `lat` and `lon`.
Which routes the browser may reach is now stated in `docs/api-surface.md` and
enforced by a generated route manifest.

**v1.7 changes from v1.6:** `GET /` adds `encoder_version` and `model_source`;
`/dashboard/summary` adds `data_provenance`; `POST /predict/point` adds
`mask_applied`, `mask_decision`, `raw_score` and `final_score`.

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

**No imagery returns `404`** with the same flat body. `POST /predict/point`
at a location with no real Sentinel-2 pixels (outside the served mosaic, or a
gap where any band is zero or missing) answers:

```json
{
  "error_code": "no_imagery_at_location",
  "detail": "Sentinel-2 mosaic does not cover (21.2667, 79.0)",
  "remedy": "Location falls outside imagery footprint. See /prospectivity/heatmap for served coverage."
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

Error codes: `model_not_loaded`, `data_not_loaded`, `prediction_failed` (all
`500`), `not_implemented` (`501`), `no_imagery_at_location` (`404`).

**`GET /` carries the served model.** `{status, version, model_version,
model_source, encoder_version, provenance_bound, degraded}`. `status` is
`"degraded"` - and `degraded` lists what - when the database and the model
registry disagree about a published artifact, or the active pointer cannot be
followed; the API keeps serving the shipped model rather than going down.

`encoder_version` is the autoencoder's digest prefix. It is reported separately
from `model_version` because 64 of the model's 78 features ARE that encoder's
latent space: the same bundle under a different encoder is a different model,
and the feature NAMES (`ae_0` … `ae_63`) do not change to say so.

`provenance_bound` is `false` when the served bundle records no training inputs.
Such a bundle is still served, but nothing can check that the raster and encoder
behind it now are the ones it learned from, so the pairing is unverified rather
than verified. The shipped `prospectivity_v6` predates provenance binding and
reports `false`; artifacts published by `POST /train` record digests for the
training raster and the encoder, and inference refuses to score when either has
drifted.

**An empty result is `200`, never an error.** A date filter matching no months
returns `series: []` with `coverage.months_present: 0`.

**Months are `YYYY-MM` strings** throughout. Tonnages are floats in tonnes.

**Authentication is required.** The server refuses to start without `API_KEY`,
and every route - `GET /` included - requires that value in the `X-API-Key`
header. A missing or wrong key is `401` with the usual flat body:
`{"error_code": "unauthorized", "detail": "missing or invalid API key", "remedy": "..."}`.
Only the OpenAPI document and `/docs` stay reachable without it, so the schema
can be read in a browser; they expose no data.

**`POST /train` queues one job for the Celery worker.** `202` with the job id,
`409 training_in_progress` while a job is queued or running, `503
broker_unavailable` when the broker cannot be reached (nothing is left queued).
`GET /train/{task_id}` reports `queued`, `running`, `completed` or `failed`; a
job whose worker died reads as `failed` once its lease lapses. A completed job's
`detail` names the version it published, and its `result_data` carries
`{version, model_path, activated}`. `activated: false` - the default - means the
artifact is in the registry and serving still uses the previously active
version until `python -m scripts.promote_model <version>` says otherwise.

**`GET /prospectivity/heatmap` can answer `503 service_busy`.** Two uncached
grids are scored at a time; a third waits, and is refused rather than queued
indefinitely. Cached viewports - everything the startup warmer holds - are
unaffected.

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
      "type_note": null,
      "lat": 21.8333,
      "lon": 80.2333,
      "confidence": "high",
      "source": "MoEFCC PFR boundary centroid + subsidence report (forestsclearance.nic.in)",
      "source_url": null,
      "coordinate_precision": null,
      "coordinate_note": null
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

**Coordinates and provenance (v1.8).** Every mine carries `lat`, `lon`,
`confidence`, `source`, `source_url`, `coordinate_precision` and
`coordinate_note`. All keys are always present.

| field | meaning |
|---|---|
| `confidence` | `high`, `medium_high`, `low_medium`, `low` or `none` |
| `source` | the named source of the coordinate |
| `source_url` | full URL, or **`null`** where no full URL has been provided (never a truncated link) |
| `coordinate_precision` | `null`, or a string such as `"approximate — town centroid, mine may be 1-3 km offset"` |
| `coordinate_note` | the source's own note where it has one (Kandri, Sitapatore), else a caution for `low` / `low_medium` / approximate coordinates, else `null` |

Current tiers: **high** for Balaghat, Ukwa, Chikla, Gumgaon, Kandri and
Sitapatore; **medium_high** for Munsar; **low_medium** for Dongri Buzurg and
Tirodi (settlement proxies); **low** for Beldongri (a third-party USGS
database).

Render `low` and `low_medium` markers so they do not read as surveyed mine
boundaries, and show `coordinate_note` as a tooltip. Sitapatore sits in
Madhya Pradesh / Balaghat (MOIL Mining Plan coordinate), so `MP` counts 4 and
`MH` 6. Full provenance: `docs/moil_coordinate_sources.md`.

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

Forecast of MH+MP production from whichever model wins the backtest at the
requested horizon. Both models were scored on the same rolling origins.

| horizon | `model_used` | `reason` | backtest MAPE, served vs alternative |
|---|---|---|---|
| 1 | `seasonal_naive` | `seasonal_naive_beats_prophet_at_short_horizon` | 9.67 vs Prophet 10.93 |
| 3 | `seasonal_naive` | `seasonal_naive_beats_prophet_at_short_horizon` | 10.05 vs Prophet 11.74 |
| 6 | `seasonal_naive` | `seasonal_naive_beats_prophet_at_short_horizon` | 10.71 vs Prophet 12.54 |
| 12 | `prophet` | `prophet_beats_seasonal_naive_at_long_horizon` | 9.92 vs naive 10.16 |

Seasonal-naive predicts **the same calendar month one year earlier**. If that
month is one of the series gaps, the horizon falls back to Prophet with
`reason: "seasonal_naive_base_month_missing"`. For the current series the base
months (2025-06 to 2025-11) are all present, so this does not occur today.

**Query params**

| name | type | default | rules |
|---|---|---|---|
| `horizon` | int | `1` | one of `1, 3, 6, 12`; else `422` |

**Response `200`**

```json
{
  "forecast_date": "2026-09-13",
  "target_period": "2026-06",
  "horizon_months": 1,
  "predicted_tonnes": 203731.48,
  "predicted_lower_ci": 181379.63,
  "predicted_upper_ci": 250086.88,
  "ci_level": 0.80,
  "series": [
    {"month": "2026-06", "month_label": "Jun 2026",
     "p10": 181379.63, "p50": 203731.48, "p90": 250086.88}
  ],
  "components": {"same_month_last_year_tonnes": 203731.48},
  "model": {
    "version": "seasonal_naive_v1",
    "variant": "seasonal_naive",
    "regressors": [],
    "trained_through": "2026-05",
    "changepoint_prior_scale": null,
    "mcmc_samples": null,
    "interval_method": "empirical_backtest_ratio_quantiles"
  },
  "model_used": "seasonal_naive",
  "reason": "seasonal_naive_beats_prophet_at_short_horizon",
  "accuracy_at_horizon": {
    "mape": 9.67,
    "naive_mape": 9.67,
    "prophet_mape": 10.93,
    "skill_vs_naive_pp": 0.0,
    "ci80_coverage": 76.0,
    "rmse": 21856.45,
    "n_origins": 25
  },
  "series": [
    {"month": "2026-06", "month_label": "Jun 2026", "p10": 176543.21, "p50": 201283.82, "p90": 227110.23}
  ]
}
```

At `horizon=12` the shape is identical, with Prophet's values:
`model.version` `prophet_baseline_v1.0`, `variant` `vanilla`,
`changepoint_prior_scale` `0.25`, `mcmc_samples` `300`, `interval_method`
`mcmc_posterior`, and `components` holding Prophet's terms (`trend`, `yearly`,
`additive_terms`, `multiplicative_terms`).

**`series`** carries one point per month of the horizon, oldest first, starting
at the month after `trained_through` and ending at `target_period`. The last
entry equals the top-level `predicted_tonnes` / `predicted_lower_ci` /
`predicted_upper_ci`, so a chart can plot `series` alone. `p50` is the point
estimate, `p10` and `p90` the bounds of the same 80% interval named by
`ci_level`.

Two properties worth knowing:

- **Intermediate months borrow the nearest backtested interval.** Only
  horizons 1, 3, 6 and 12 were backtested, so month 2 uses the 1-month interval
  ratios and month 5 the 3-month ones — always the nearest backtested horizon
  *at or below* the month. Borrowing downward is the conservative direction: a
  shorter horizon has the tighter interval, so no interval is widened on
  evidence that does not exist.
- **`series` is `[]` when a month inside the horizon has no base.**
  Seasonal-naive needs the same calendar month a year earlier; if one of those
  is a series gap, the whole series is withheld rather than served with a hole
  in it. The terminal point is still returned, so `predicted_tonnes` remains
  usable.

`components` keys vary with the model. Seasonal-naive has one,
`same_month_last_year_tonnes`. The shipped Prophet variant has **no rainfall or
capex component**. The frontend must iterate whatever keys arrive rather than
index fixed names.

`accuracy_at_horizon` describes **the model actually served**: `mape`, `rmse`
and `ci80_coverage` are that model's backtest figures. `naive_mape` and
`prophet_mape` are always both present, so the UI can show the comparison.
`skill_vs_naive_pp` is `naive_mape − mape`: `0.0` when seasonal-naive is
served, `+0.24` at 12. In v1.6 these fields were always Prophet's; read
`prophet_mape` for Prophet's figure.

**Intervals** differ by model, and `model.interval_method` names which:

- `mcmc_posterior` (Prophet): coverage 71.4% at 12 months against a nominal
  80%; known to be too tight, and recalibration is open work.
- `empirical_backtest_ratio_quantiles` (seasonal-naive): the 10th–90th
  percentile of actual ÷ naive across the backtest origins at that horizon.
  `ci80_coverage` is measured **leave-one-out** (76.0 / 73.9 / 70.0% at 1 / 3 /
  6), not in-sample, where it would be ~80% by construction. The interval is
  asymmetric: production has mostly run above the same month last year over
  the backtest window, so the upper side is wider. The point forecast
  deliberately excludes that growth. A trend-adjusted naive was backtested and
  rejected; it scored 13.00 MAPE at horizon 1, worse than Prophet.

**Shortfall is still defined against Prophet.** `/shortfall/risk` compares
production with `prophet_forecast_tonnes`, because the classifier was trained
on that definition. For 2026-06 the value `/forecast` serves (seasonal-naive)
and the shortfall reference (Prophet) are different numbers. Do not render the
shortfall threshold as 90% of `/forecast`'s `predicted_tonnes`.

```bash
curl "http://127.0.0.1:8000/forecast?horizon=12"
```

---

## 5. `GET /forecast/history`

Backtest metrics per horizon for both models, so the routing in `/forecast`
can be checked against the evidence.

**No query params.**

**Response `200`**

```json
{
  "horizons": [
    {"horizon_months": 1, "n_origins": 25, "mape": 10.93, "rmse": 25320.45,
     "naive_mape": 9.67, "skill_vs_naive_pp": -1.26, "ci80_coverage": 64.0,
     "comparison": {
       "prophet_mape": 10.93, "seasonal_naive_mape": 9.67,
       "prophet_rmse": 25320.45, "seasonal_naive_rmse": 21856.45,
       "prophet_ci80_coverage": 64.0, "seasonal_naive_ci80_coverage": 76.0,
       "better_model": "seasonal_naive", "model_used": "seasonal_naive",
       "routing_matches_backtest": true
     }},
    {"horizon_months": 12, "n_origins": 14, "mape": 9.92, "rmse": 25948.46,
     "naive_mape": 10.16, "skill_vs_naive_pp": 0.24, "ci80_coverage": 71.4,
     "comparison": {
       "prophet_mape": 9.92, "seasonal_naive_mape": 10.16,
       "prophet_rmse": 25948.46, "seasonal_naive_rmse": 23416.10,
       "prophet_ci80_coverage": 71.4, "seasonal_naive_ci80_coverage": 71.4,
       "better_model": "prophet", "model_used": "prophet",
       "routing_matches_backtest": true
     }}
  ],
  "origins": [
    {"horizon_months": 1, "origin_month": "2024-04", "target_month": "2024-05",
     "actual_tonnes": 168090.0, "predicted_tonnes": 213318.40,
     "seasonal_naive_tonnes": 180112.0, "covered": false}
  ],
  "model": {"version": "prophet_baseline_v1.0", "variant": "vanilla"},
  "benchmark": {"name": "seasonal_naive", "definition": "same calendar month one year earlier"},
  "routing": {
    "seasonal_naive_max_horizon": 6,
    "rule": "horizons <= 6 months are served by seasonal_naive, longer horizons by prophet"
  }
}
```

Measured comparison, all four horizons:

| horizon | Prophet MAPE | naive MAPE | Prophet RMSE | naive RMSE | Prophet CI80 | naive CI80 (LOO) | served |
|---|---|---|---|---|---|---|---|
| 1 | 10.93 | **9.67** | 25,320 | 21,856 | 64.0 | 76.0 | `seasonal_naive` |
| 3 | 11.74 | **10.05** | 27,971 | 22,606 | 65.2 | 73.9 | `seasonal_naive` |
| 6 | 12.54 | **10.71** | 29,973 | 23,992 | 60.0 | 70.0 | `seasonal_naive` |
| 12 | **9.92** | 10.16 | 25,948 | 23,416 | 71.4 | 71.4 | `prophet` |

At 12 months seasonal-naive has the lower RMSE but the higher MAPE. Routing
follows MAPE, the metric the shipped backtest ranks by.

The top-level horizon fields (`mape`, `rmse`, `naive_mape`,
`skill_vs_naive_pp`, `ci80_coverage`) keep their v1.6 meaning: Prophet's
backtest. `comparison` holds both models side by side.

`origins` is the per-origin detail (82 rows across four horizons) for plotting
actual-vs-predicted. `predicted_tonnes` and `covered` are Prophet's;
`seasonal_naive_tonnes` is the naive prediction for the same origin. If the
frontend only needs the summary, read `horizons`.

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
    "month": "2026-06", "predicted_tonnes": 203731.48,
    "lower_ci": 181379.63, "upper_ci": 250086.88, "ci_level": 0.80,
    "model_used": "seasonal_naive"
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
  "mines": {"total": 10, "underground": 7, "opencast": 3},
  "degraded": [],
  "data_provenance": {
    "origin": "shipped trained models",
    "synthetic": false,
    "note": null,
    "prospectivity_model": "prospectivity_v6",
    "prospectivity_model_source": "shipped",
    "encoder": "24c39a1c97f1",
    "prospectivity_provenance_bound": false,
    "forecast_model": "prophet_baseline_v1.0",
    "shortfall_model": "shortfall_classifier_v1"
  }
}
```

`next_forecast` is `/forecast?horizon=1`, which seasonal-naive serves;
`model_used` says so. `model_health.forecast_version` still names the Prophet
bundle, which serves horizon 12 and underlies `/shortfall/risk`.
`data_provenance` is always present, and it decides how the screen labels
itself. `synthetic: true` means artifacts failed to load and what is shown is
NOT the shipped trained output; `note` then says which. The frontend treats a
missing block as a fault rather than as "production", so this key is never
omitted. `prospectivity_provenance_bound` mirrors `GET /`'s `provenance_bound`:
`false` means the served bundle records no training inputs, so the raster and
encoder behind it are unverified.

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

This endpoint exists because `POST /predict/points_in_bbox` (formerly
`/predict/bbox`, section 11) cannot feed a map: it
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

`mask` uses the **same vocabulary as `/predict/point` and `/predict/points_in_bbox`**
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
falls outside the imagery footprint, **or** when any of its six Sentinel-2
bands is missing or zero (a composite gap). The second case matters: under v1, `/predict/point` returned the
capped score `0.990` for such cells, so Kandri and Beldongri - both just
outside the footprint - scored as maximum prospectivity on no data at all. A
heatmap that rendered those would put its two brightest hotspots where nothing
was measured. Before v1.8, v6 returned `0.0009` there from a blank
national-tile patch. The API also scored from a mosaic whose gaps read as
zero reflectance, fabricating about a quarter of the warm heatmap
(`docs/known_issues.md` #6 and #7). Both are fixed: these cells are now `null`,
and `/predict/point` answers `404 no_imagery_at_location`.

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

**Colour-ramp note:** under the promoted v6 bundle, **23.9–43.9% of cells
score at or above 0.90** depending on the viewport, and 17–33% sit exactly at
the 0.99 cap (measured on the corrected serving mosaic; the earlier 24.5%
figure came from the wrong mosaic). A linear 0–0.99 ramp renders a large share
of the map at one maximum colour. A percentile-based or non-linear ramp separates
the top of the distribution far better. See
`docs/frontend_heatmap_guidance.md` for measured distributions per viewport
and recommended breakpoints.

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

## 11. `POST /predict/points_in_bbox` (renamed from `/predict/bbox`)

A Phase 2 endpoint, renamed in v1.7 to say what it returns: a **score-sorted
list of candidate points**, not a grid (`docs/known_issues.md` #1). Request
and response bodies are unchanged.

| path | status | behaviour |
|---|---|---|
| `POST /predict/points_in_bbox` | current | — |
| `POST /predict/bbox` | deprecated alias | identical body, plus response header `X-Deprecated: use-predict-points-in-bbox`; `deprecated: true` in OpenAPI |

The header is set on successful responses. A `422` from the old path carries
FastAPI's standard error body without it.

For map rendering use `GET /prospectivity/heatmap` (section 10).

```bash
curl -X POST "http://127.0.0.1:8000/predict/points_in_bbox" \
  -H "Content-Type: application/json" \
  -d '{"min_lon": 80.10, "min_lat": 21.75, "max_lon": 80.25, "max_lat": 21.85, "grid_resolution_m": 5000}'
```


---

## 12. `POST /predict/point` — uncapped classifier output (v1.10)

Two additive fields on the existing response body. Nothing else about the
endpoint changes.

| field | type | meaning |
|---|---|---|
| `raw_probability` | `float \| null` | `predict_proba` from the XGBoost bundle, **before** the Elkan-Noto PU adjustment and before the cap. Range `0–1`. |
| `model_margin` | `float \| null` | The same prediction in log-odds (`output_margin=True`). Unbounded; measured `2.27` to `5.85` across the ten shortlisted targets. |

They are related exactly: `raw_probability == 1 / (1 + exp(-model_margin))`,
asserted by `test_predict_point_exposes_the_uncapped_classifier_output`.

**Why they exist.** `prospectivity_score` divides the raw probability by the
PU constant `c = 0.9049` and then caps the result at `0.99`, so **any raw
probability at or above `0.8959` displays as `0.99`**. That is not a rounding
artefact at the edge of the distribution — it is most of the interesting
ground: all ten greenfield targets the Explorer shortlists sit on the cap
while their raw probabilities span `0.907–0.997`. Ranked on the served score
alone the list is a ten-way tie, and any order shown is the order the array
happened to be in.

`model_margin` is the field to rank on. It comes from the model rather than
from a client-side heuristic, and it separates locations the cap has merged.
`raw_probability` is the field to *display* beside the score when a user needs
to see that two capped locations are not equally strong.

Both are `null`-able in the contract and absent on a pre-v1.10 backend. A
client must not reorder a list from a partial set of margins — either every
entry has one or the existing order stands, otherwise the list mixes two
orderings and reads as neither.

```bash
curl -X POST "http://127.0.0.1:8000/predict/point?mask=none"   -H "Content-Type: application/json"   -d '{"lat": 21.8000, "lon": 80.1900}'
```

```json
{
  "prospectivity_score": 0.99,
  "raw_score": 0.99,
  "final_score": 0.99,
  "raw_probability": 0.9971,
  "model_margin": 5.849,
  "model_version": "prospectivity_v6"
}
```

Neither field is a calibrated probability of mineralisation. They describe how
far inside its positive class the classifier places a pixel, on training data
of boreholes, NGDR occurrences and foreign analogues.


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
