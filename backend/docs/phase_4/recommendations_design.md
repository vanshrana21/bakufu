# Corrective Actions Rules Engine — Design

Design for `GET /recommendations`, replacing the Bucket 1 `501` stub. The
engine is a deterministic layer over the shortfall classifier's SHAP output.
It trains nothing, adds no data source, and cannot change a prediction.

**Status: awaiting review. No code written yet.**

## 1.1 SHAP driver taxonomy

The classifier has nine features. They group into four drivers exactly as
proposed — verified against the shipped `shortfall_classifier_v1.pkl` rather
than assumed:

| driver | features | display name |
|---|---|---|
| `rainfall_signal` | `rainfall_lag2_mm`, `rainfall_lag1_mm`, `rainfall_concurrent_mm` | Rainfall and monsoon impact |
| `production_history_signal` | `deviation_lag1`, `deviation_lag2`, `production_trend_3mo` | Recent production performance |
| `forecast_level_signal` | `prophet_forecast_level` | Forecast output level |
| `seasonal_signal` | `month_sin`, `month_cos` | Seasonal position |

### A correction to the proposed ranking rule

The brief suggests selecting the top driver by **sum of |SHAP|**. Measured
against the current live prediction, that rule picks the wrong driver.

Current state (`p = 0.1073`, risk level `low`):

| feature | value | SHAP | direction |
|---|---|---|---|
| `deviation_lag1` | +7.4% | **−1.5043** | decreases risk |
| `prophet_forecast_level` | 201,284 t | **−1.1578** | decreases risk |
| `rainfall_lag2_mm` | 1.5 mm | **+1.0273** | *increases* risk |
| `production_trend_3mo` | +11.7% vs prior quarter | −0.4871 | decreases risk |
| `rainfall_lag1_mm` | 4.0 mm | +0.3199 | *increases* risk |
| `month_sin` | 0.000 | −0.2279 | decreases risk |
| `month_cos` | −1.000 | −0.0590 | decreases risk |
| `rainfall_concurrent_mm` | 100.0 mm | −0.0323 | decreases risk |
| `deviation_lag2` | +1.0% | +0.0157 | increases risk |

Aggregated by driver:

| driver | Σ&#124;SHAP&#124; | Σ positive SHAP (risk-increasing) |
|---|---|---|
| `production_history_signal` | **2.0071** | +0.0157 |
| `rainfall_signal` | 1.3795 | **+1.3472** |
| `forecast_level_signal` | 1.1578 | 0.0 |
| `seasonal_signal` | 0.2870 | 0.0 |

Ranking by |SHAP| names `production_history_signal` the top driver — but every
one of its large contributions is **negative**: last month came in 7.4% *above*
forecast and the 3-month trend is *up* 11.7%. That driver is currently the
strongest reason to expect no shortfall. Firing corrective actions against it
would tell an operator to fix the thing that is going well.

**Ranking rule: sum of positive SHAP per driver**, i.e. only contributions that
push risk *up*. Falling back to |SHAP| when no feature is positive is
unnecessary, because that case is exactly when no corrective action is
warranted, and the low-risk branch in §1.4 already returns an empty list.

Under this rule the current top driver is `rainfall_signal` (+1.3472), which is
correct: the only things arguing for a shortfall right now are the two lagged
rainfall terms.

> **Principle.** Only features with positive SHAP (arguing FOR shortfall)
> generate corrective actions. Features with negative SHAP describe why the
> forecast is currently healthy and do not warrant intervention.

## 1.2 Rule template catalog

32 templates. Equipment nouns come **only** from `UNDERGROUND_FLEET_VOCAB` and
`OPENCAST_FLEET_VOCAB` in `src/reference/moil_mines.py`:

```
UG: SDL, rocker_shovel, electro_hydrostatic_drill,
    hydraulic_sand_stowing, shaft_sinking_rig, rock_mechanics_monitoring
OC: hydraulic_shovel_0.9_to_1.7_m3, drill_100mm, dumper_20_to_25t,
    water_tanker_sprinkler, bench_management
```

Public sources record no LHD, jumbo drill or 100-tonne dumper at any MOIL mine,
so those words must never appear in a card.

Each template carries `id`, `action_type`, `title`, `rationale_template`,
`equipment_referenced`, `priority`, `applicable_mine_types`.

### rainfall_signal × underground (6)

| id | action_type | title | priority |
|---|---|---|---|
| `ug_rain_stowing_capacity` | equipment_redeployment | Bring forward hydraulic sand stowing capacity | high |
| `ug_rain_shift_sequence` | schedule_adjustment | Re-sequence development shifts away from wet-season faces | high |
| `ug_rain_blast_window` | blasting_optimization | Shorten blast-to-mucking window while inflow is elevated | medium |
| `ug_rain_sdl_allocation` | equipment_redeployment | Reallocate SDL units to drier levels | medium |
| `ug_rain_strata_watch` | schedule_adjustment | Increase rock mechanics monitoring cadence after heavy rain | medium |
| `ug_rain_charge_protection` | blasting_optimization | Switch to moisture-resistant charging practice | medium |

Sample rationale (`ug_rain_stowing_capacity`):
> Rainfall two months ago ({rainfall_lag2_mm} mm) is the largest single factor
> raising this month's shortfall risk. Stowing throughput limits how quickly
> worked-out faces are returned to production after wet-season inflow.

### rainfall_signal × opencast (6)

| id | action_type | title | priority |
|---|---|---|---|
| `oc_rain_bench_drainage` | schedule_adjustment | Pull forward bench drainage and haul-road repair | high |
| `oc_rain_dumper_rotation` | equipment_redeployment | Rotate 20–25 t dumpers onto hardened haul segments | high |
| `oc_rain_blast_timing` | blasting_optimization | Move blasts to the driest window in the shift pattern | high |
| `oc_rain_shovel_reposition` | equipment_redeployment | Reposition hydraulic shovels to higher benches | medium |
| `oc_rain_hole_dewatering` | blasting_optimization | Dewater 100 mm blast holes before charging | medium |
| `oc_rain_sprinkler_standdown` | schedule_adjustment | Stand down water tankers during wet periods | low |

### production_history_signal × underground (4)

| id | action_type | title | priority |
|---|---|---|---|
| `ug_hist_face_rebalance` | schedule_adjustment | Rebalance shift allocation toward underperforming faces | high |
| `ug_hist_sdl_uplift` | equipment_redeployment | Concentrate SDL capacity on the highest-grade faces | high |
| `ug_hist_blast_cycle` | blasting_optimization | Tighten the drill-and-blast cycle on lagging faces | medium |
| `ug_hist_drill_pilot` | equipment_redeployment | Extend the electro-hydrostatic drill pilot | low |

### production_history_signal × opencast (4)

| id | action_type | title | priority |
|---|---|---|---|
| `oc_hist_strip_ratio` | schedule_adjustment | Re-plan the stripping schedule against the shortfall | high |
| `oc_hist_shovel_dumper_match` | equipment_redeployment | Rematch shovel and dumper fleet sizing | high |
| `oc_hist_fragmentation` | blasting_optimization | Review fragmentation against dig rates | medium |
| `oc_hist_bench_height` | schedule_adjustment | Revisit bench height on the lagging pit | low |

### forecast_level_signal × underground (4)

| id | action_type | title | priority |
|---|---|---|---|
| `ug_level_shaft_priority` | schedule_adjustment | Prioritise shaft-sinking milestones against the target | high |
| `ug_level_hoisting_window` | equipment_redeployment | Extend hoisting windows to match the forecast level | medium |
| `ug_level_round_length` | blasting_optimization | Increase advance per round on main development | medium |
| `ug_level_stowing_balance` | equipment_redeployment | Balance stowing against planned extraction | low |

### forecast_level_signal × opencast (4)

| id | action_type | title | priority |
|---|---|---|---|
| `oc_level_dumper_cycle` | schedule_adjustment | Compress dumper cycle times to meet the forecast level | high |
| `oc_level_shovel_hours` | equipment_redeployment | Add hydraulic shovel hours on the primary bench | medium |
| `oc_level_powder_factor` | blasting_optimization | Review powder factor against the production target | medium |
| `oc_level_bench_prep` | schedule_adjustment | Advance bench preparation ahead of the target month | low |

### seasonal_signal × underground (2)

| id | action_type | title | priority |
|---|---|---|---|
| `ug_season_premonsoon_prep` | schedule_adjustment | Complete pre-monsoon stowing and pumping readiness | high |
| `ug_season_blast_calendar` | blasting_optimization | Align the blast calendar to the seasonal pattern | medium |

Plus `ug_season_equipment_stage` (equipment_redeployment, medium): *Stage SDL
and rocker shovel spares before the monsoon window.*

### seasonal_signal × opencast (2)

| id | action_type | title | priority |
|---|---|---|---|
| `oc_season_haul_hardening` | schedule_adjustment | Harden haul roads before the monsoon window | high |
| `oc_season_blast_frontload` | blasting_optimization | Front-load blasting ahead of the wet season | high |

Plus `oc_season_fleet_shelter` (equipment_redeployment, medium): *Stage dumper
and shovel maintenance for the low-production window.*

**Coverage check:** all 8 driver × mine-type combinations carry at least one
rule of each `action_type` — 24 mandatory, 32 total for variety.

## 1.3 Aggregation and ranking

1. Split `feature_contributions` into risk-increasing (`shap > 0`) and
   risk-decreasing.
2. Aggregate positive SHAP per driver. Rank drivers descending.
3. Take the top 1–2 drivers depending on the risk band (§1.4).
4. Filter the catalog to rules whose `applicable_mine_types` includes the
   resolved mine type (underground for an unspecified mine — 7 of 10 MOIL
   mines are underground).
5. **Enforce the PS-coverage guarantee** at `p >= 0.60`: if the ranked
   selection is missing an `action_type`, pull the highest-priority rule of
   that type from the top driver, then from the second driver. This is
   enforced in the engine, not left to selection luck.
6. Sort by `(priority rank, |SHAP| of the driver's strongest positive
   feature)`, then truncate to `limit`.

Rationale placeholders are filled from the matching feature's `display_value`
in the shortfall response, so a card quotes the same number the risk panel
shows.

## 1.4 Edge cases

| condition | behaviour |
|---|---|
| `p < 0.25` (low) | empty `recommendations`, `context.message`: *"No corrective action needed at current risk level."* |
| `0.25 <= p < 0.60` (medium) | top 1–2 rules from the **primary driver only**; no action-type guarantee |
| `p >= 0.60` (high) | full set, **all three action types guaranteed** |
| `mine_name` null | aggregate view; underground vocabulary (the majority type), `context.mine_name` null |
| `mine_name` unknown | `422`, consistent with Bucket 1 |
| generic-fleet mine | resolves by `mine_type`, so Sitapatore and Dongri Buzurg get opencast rules; the placeholder `standard_*_fleet` token never reaches a card |
| no positive SHAP at all | treated as low risk regardless of `p` — nothing is arguing for a shortfall |

### Two conflicts worth your decision

**`limit < 3` at high risk cannot satisfy the coverage guarantee.**
Resolved: **`limit` wins**, and the truncated set preserves *action-type
diversity* rather than taking top-N by priority alone. At `limit=2` the engine
takes the top rule from the highest-priority action type, then the top rule
from a **different** action type. The response carries:

```json
{"coverage_complete": false,
 "action_types_included": ["schedule_adjustment", "equipment_redeployment"],
 "action_types_omitted": ["blasting_optimization"]}
```

At `limit=1` the same applies with a single action type included.

**Current state produces zero recommendations.** `p = 0.1073` is below the
0.25 floor, so `/recommendations` returns an empty list with the "no corrective
action needed" message. That is correct, and is what makes the engine
trustworthy — but a reviewer would never see a populated card.

Resolved with `GET /recommendations/scenario/{month}` rather than a
`simulate_probability` query parameter. The scenario endpoint re-runs the real
classifier over a real historical month's features and returns recommendations
from the actual SHAP output. No fabricated inputs, and nothing demo-only left
in the production surface.

`SCENARIO_MONTHS` lives in `settings.py` so the picks can be swapped without a
code change. A month outside the list returns `404`.

### Scenario month selection

The brief suggested `2018-05` and `2020-04`. Neither is available: the
classifier's feature table begins at **2021-04**, because the
`min_train_for_label = 60` cut excluded the early origins where a young Prophet
manufactured artefactual shortfalls. All 13 real shortfalls in that window are
flagged by the model at `p >= 0.60`. Ranked by how many drivers contribute
positive SHAP:

| month | p | drivers active | rain | hist | level | seasonal |
|---|---|---|---|---|---|---|
| **2021-04** | 0.910 | 4 | **1.567** | 1.441 | 0.096 | 0.379 |
| **2024-02** | 0.991 | 4 | 0.740 | 1.601 | **2.247** | 0.301 |
| 2025-02 | 0.952 | 4 | 1.386 | 1.105 | 1.684 | 0.163 |
| 2022-10 | 0.892 | 3 | 0.093 | 2.828 | 0.000 | 0.152 |

**Picked `2021-04` and `2024-02`** — deliberately different shapes:
`2021-04` is **rainfall-led** (rain 1.567 outranks history 1.441), so the cards
lead with monsoon actions and the physical mechanism shows through.
`2024-02` is **forecast-level-led** (2.247), so it produces a different card
set built around hitting an ambitious target. Together they demonstrate the
driver taxonomy actually switching, rather than one canned response.

## Constraints honoured

- no new models, no new data sources, no retraining
- `/shortfall/risk` unmodified; the engine consumes its response shape only
- every `equipment_referenced` value drawn from the two MOIL vocabularies
- no vague outputs: every rule names a concrete action
