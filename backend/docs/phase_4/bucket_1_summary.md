# Phase 4, Bucket 1 — Backend complete

**Contract version:** v1.5 (superseded by v1.6 — see `bucket_2_summary.md`) (`docs/phase_4/api_contracts.md`)
**Test suite:** 194 passed, 1 skipped
**Date:** 2026-09-10

Every endpoint serves real data from promoted artifacts. No mocked responses,
no placeholder values, no Supabase tables added.

## Endpoints

24 operations registered. `test_all_expected_routes_are_registered` pins the
exact set and fails if one disappears *or* an undocumented one appears.

### Phase 4 — dashboard (new or rewired)

| Method | Route | Status | Serves |
|---|---|---|---|
| GET | `/production/history` | ready | 123-month MSMP series, window-scoped coverage |
| GET | `/mines` | ready | 10 MOIL mines + honest-story counts |
| GET | `/mines/{mine_name}` | ready | one mine + fleet vocabulary |
| GET | `/forecast` | ready | Prophet forecast at horizon 1/3/6/12 |
| GET | `/forecast/history` | ready | 4 horizon rows + 82 backtest origins |
| GET | `/shortfall/risk` | ready | next-month risk + 9-feature SHAP explanation |
| GET | `/dashboard/summary` | ready | landing aggregate, degrades per component |
| GET | `/prospectivity/heatmap` | ready | 32×32 score lattice for the map |
| POST | `/forecast/retrain` | **501 stub** | disabled in demo mode |
| GET | `/recommendations` | **implemented in Bucket 2** | see `bucket_2_summary.md` |

### Phase 1/2 — unchanged, still passing

| Method | Route |
|---|---|
| GET | `/` (health) |
| GET | `/boreholes`, `/boreholes/{id}`, `/boreholes/{id}/features` |
| GET | `/priors`, `/priors/{block_name}` |
| GET | `/foreign` |
| GET | `/masks`, `/predictions/{prediction_id}` |
| POST | `/predict/point`, `/predict/bbox` |
| POST | `/train` · GET `/train/{task_id}` |
| GET | `/forecast/retrain/{task_id}` |

Two Phase 2 tests were updated, both for deliberate schema changes rather than
regressions: the health test hardcoded version `0.1` (now `0.2`, asserted
against the constant), and `/production/history` moved from the 20-row BSE
list to the MSMP object. Both changes were agreed before they were made.

## Model artifacts served

Endpoints read **promoted** files only. Training writes elsewhere and
promotion is a manual copy — this split exists because a training run once
overwrote the served forecast model and the API silently served a rejected
variant while returning `200`.

| purpose | artifact |
|---|---|
| forecast model | `models/prophet_baseline_v1_0_shipped.pkl` |
| forecast metrics | `data/processed/prophet_metrics_baseline_v1_0.json` |
| backtest origins | `data/processed/prophet_backtest_rows_baseline_v1_0.parquet` |
| shortfall model | `models/shortfall_classifier_v1.pkl` |
| prospectivity model | `models/prospectivity_v6.pkl` (promoted from v1) |
| production series | `data/processed/msmp_mn_monthly_wide.parquet` |

Artifacts load eagerly in the FastAPI lifespan handler into `app.state`. A
load failure is recorded per-artifact and surfaces as `500 model_not_loaded`
from the endpoints that need it, so one missing file cannot take the API down.

## Cache warming

Warming runs **asynchronously** on a daemon thread at startup. The API is
available immediately; warming three heatmap viewports inline would block
startup for roughly two minutes.

| what | cold | warm | strategy |
|---|---|---|---|
| `/forecast` (×4 horizons) | ~0.96 s each | 2–37 ms | in-process memo, warmed at startup |
| `/shortfall/risk` | ~6.6 s | 2–37 ms | in-process memo **+ disk**, 24 h TTL |
| `/prospectivity/heatmap` | ~38 s | ~36 ms | disk cache, 24 h TTL, 3 viewports warmed |
| `/dashboard/summary` | — | ~45 ms | composes the memoised components |

Pre-warmed viewports (`settings.HEATMAP_WARM_VIEWPORTS`), all fully inside the
usable raster footprint so none contain null cells:

- `full_bbox` `[79.0, 21.3, 80.6, 22.1]`
- `balaghat_bhandara` `[79.53, 21.32, 80.57, 22.05]`
- `balaghat_ukwa` `[80.05, 21.70, 80.60, 22.05]`

Cache keys include the **model version**, so a promotion cannot serve stale
tiles. The shortfall key includes both `as_of` and `forecast_month`, so a new
MSMP month correctly misses. Cache files live in `data/cache/` and are
gitignored — they regenerate on demand.

## Known limitations

Full evidence for each is in `docs/known_issues.md`.

**Three MOIL mines cannot be scored.** Gumgaon (21.23), Kandri (21.26) and
Beldongri (21.28) sit south of the DEM's hard edge at 21.3000. Extending the
bbox south *loses* 128 cells rather than gaining coverage, because Sentinel-2
reaches only 0.011° further and has no elevation beneath it. The frontend
renders these mine markers outside the raster with a tooltip explaining the
scope limit. Accepted, not fixed — it is an imagery-acquisition constraint.

**Forecast intervals are too narrow.** CI80 coverage runs 60.0–71.4% against a
nominal 80%. MCMC sampling lifted it ~12 pp over analytical intervals but did
not close the gap. `/forecast` returns `ci80_coverage` so the UI can state the
real figure. Options: recalibrate empirically from backtest residuals, or
relabel as 70% intervals.

**The forecast loses to seasonal-naive at short horizons.** `skill_vs_naive_pp`
is −1.26, −1.69 and −1.84 at 1, 3 and 6 months, and **+0.24 at 12 months**
(MAPE 9.92%). This is a real property of a series with strong year-over-year
persistence, exposed structurally in the API so the UI cannot overclaim.

**The prospectivity map needs a non-linear colour ramp.** Under v6, 24.5% of
cells score ≥0.90. A linear 0–0.99 ramp renders roughly a quarter of the map
at maximum intensity. Use discrete bins or a percentile-based scale.

**Cold response times exceed the general 500 ms target** for `/forecast`
(~0.96 s), `/shortfall/risk` (~6.6 s) and `/prospectivity/heatmap` (~38 s,
documented separately at 5 s warm / 45 s cold). Warming means a real request
should never pay these, but a cache miss after a 24 h TTL expiry would.

**`POST /predict/bbox` is not griddable.** It returns a score-sorted point set
whose cells are not on a lattice, with 44% falling outside the requested bbox.
Phase 2 is frozen, so `/prospectivity/heatmap` routes around it rather than
fixing it.

**Shortfall training data excludes COVID-scale shocks.** The classifier was
trained on 60 months with 13 positives from 2021-02 onward; 2020's lockdown
months fall outside that window. Behaviour on shocks of that magnitude is
untested. It is a screening tool (precision 0.33, recall 0.71), not a
prediction.

## Tests

**194 passed, 1 skipped.**

- `tests/test_api_phase4.py` — 90 tests covering the ten Phase 4 endpoints:
  contract shape, happy path, 422 validation, 500 with machine-readable error
  codes, idempotency, cache behaviour, and the route registry.
- Remaining ~103 across Phase 1–3 suites, unchanged.

The **1 skip** is `test_lstm_residual_reduces_error`: Phase 3.2e was
deferred, so `models/lstm_residual_v1.pt` does not exist. It marks unbuilt
scope, not a failure.

An earlier version of this document said the skips were DB-backed tests
needing `DATABASE_URL`. That was wrong — those tests run against Supabase
whenever the variable is set. A second skip,
`test_shortfall_classifier_beats_baseline`, was pointing at
`models/shortfall_v1.pkl`, the retired Phase 3 scaffold's path that never
existed; it now targets the shipped `shortfall_classifier_v1.pkl` and
asserts against its real contents.

## Not done, by design

- No new Supabase tables. All models load from `.pkl`, all data from parquet.
- Nothing deployed. Local FastAPI only.
- No frontend code.
- `/recommendations` returns 501 rather than a plausible fake, so the frontend
  cannot accidentally build against invented data.
