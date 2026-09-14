# Phase 4, Bucket 2 — Corrective Actions Rules Engine

**Contract version:** v1.6 (`docs/phase_4/api_contracts.md`)
**Test suite:** 238 passed, 1 skipped
**Date:** 2026-09-11

Extends Bucket 1. All 24 endpoints documented in
`docs/phase_4/bucket_1_summary.md` remain live and unchanged; this adds the
recommendations engine and one new endpoint, taking the API to **25
operations** (`/recommendations` already existed as a stub).

The engine closes three problem-statement bullets that Bucket 1 could not:
adjusting mine schedules, optimising blasting, and re-deploying equipment.

## What was built

| file | what |
|---|---|
| `src/models/recommendations/rules.py` | 32 rule templates + driver taxonomy |
| `src/models/recommendations/engine.py` | ranking, coverage guarantee, footnotes |
| `GET /recommendations` | live cards from the current shortfall explanation |
| `GET /recommendations/scenario/{month}` | replay over a real historical month |
| `tests/test_recommendations.py` | 44 tests |

No new models, no new data sources, no retraining. `/shortfall/risk` is
untouched — the engine consumes its response *shape* and nothing else, so rule
logic is testable against a hand-built response and the endpoint reuses an
already-cached explanation rather than paying the SHAP cost twice.

## Driver taxonomy

The classifier's nine features roll up into four drivers:

| driver | features | display name |
|---|---|---|
| `rainfall_signal` | `rainfall_lag2_mm`, `rainfall_lag1_mm`, `rainfall_concurrent_mm` | Rainfall and monsoon impact |
| `production_history_signal` | `deviation_lag1`, `deviation_lag2`, `production_trend_3mo` | Recent production performance |
| `forecast_level_signal` | `prophet_forecast_level` | Forecast output level |
| `seasonal_signal` | `month_sin`, `month_cos` | Seasonal position |

### Ranking: positive SHAP only

**Only features with positive SHAP — those arguing FOR a shortfall — generate
corrective actions. Features with negative SHAP describe why the forecast is
currently healthy and do not warrant intervention.**

The original design ranked drivers by Σ|SHAP|. Measured against the live
prediction, that picks the wrong driver:

| driver | Σ&#124;SHAP&#124; | Σ positive |
|---|---|---|
| `production_history_signal` | **2.0071** | +0.0157 |
| `rainfall_signal` | 1.3795 | **+1.3472** |

`production_history_signal` has the larger magnitude, but every contribution is
negative: last month came in **+7.4% above forecast** and the 3-month trend is
**up 11.7%**. Ranking by magnitude would have fired corrective actions against
the strongest reason to expect *no* shortfall.

## Rule catalog

**32 templates.** Every one of the 8 driver × mine-type combinations carries at
least one rule of each action type — 24 mandatory, 8 extra for variety.

Equipment nouns are drawn strictly from `UNDERGROUND_FLEET_VOCAB` and
`OPENCAST_FLEET_VOCAB`. Public sources record no LHD, jumbo drill or
100-tonne dumper at any MOIL mine, so generic mining vocabulary would
recommend equipment the company does not operate.
`test_rules_reference_only_moil_equipment` iterates every template to enforce
this.

## Risk bands

| probability | behaviour |
|---|---|
| `< 0.25` | empty list, explanatory message, footnotes suppressed |
| `0.25 – 0.60` | 1–2 cards from the primary driver only |
| `>= 0.60` | all three action types guaranteed, subject to `limit` |

`limit` wins over the coverage guarantee, but truncation preserves action-type
*diversity* rather than taking top-N by priority — `limit=2` returns two
different action types, and reports `coverage_complete: false` with the omitted
type named.

## Two problems found by rendering real values

**Rationales cited the wrong feature.** Templates hardcoded placeholders like
`{deviation_lag1}`, but a driver can be fired by any of its members. With real
values that produced:

> *"Recent output is the leading risk driver: last month came in at **+19.7%**
> against forecast. Rebalancing shifts targets the faces carrying the
> shortfall."*

A positive number offered as evidence of a problem. Templates now cite the
*triggering* feature via `{trigger_label}` / `{trigger_value}`, filled from the
same contribution the card reports in `triggered_by`.
`test_rationale_cites_the_triggering_feature` pins it.

**Counterintuitive contributions needed explaining.** A rising trend genuinely
can raise shortfall risk — mean reversion, where the forecast rises with recent
output so the next month must sustain a higher level — but a card quoting
"+27.1%" as a risk factor reads as a non-sequitur.

`context.footnotes` carries an explanation only when a feature's raw value
reads as good news while its SHAP pushes risk up. Three features qualify:
`production_trend_3mo` above 1.0, `deviation_lag1` and `deviation_lag2` above
zero. Rainfall, forecast level and seasonal terms are intuitive and never
trigger one. Footnotes are suppressed when no cards render.

## Demo behaviour

**Current month** (`p = 0.107`): zero recommendations, *"No corrective action
needed at current risk level."* The engine does not invent urgency, and drivers
are still ranked so the panel can show why the outlook is calm.

**`GET /recommendations/scenario/{month}`** replays a real historical month.
Rejected the alternative — a `simulate_probability` query parameter — because
it would leave demo-only code in the production API and the answer to "what
does this parameter do" is weak. The scenario endpoint uses real data through
the real model.

Configured months (`settings.SCENARIO_MONTHS`), deliberately different shapes:

**2021-04**, rainfall-led, `p = 0.910`:
```
[high  |schedule_adjustment   ] Re-sequence development shifts away from wet-season faces
[high  |equipment_redeployment] Bring forward hydraulic sand stowing capacity
[high  |schedule_adjustment   ] Rebalance shift allocation toward underperforming faces
[high  |equipment_redeployment] Concentrate SDL capacity on the highest-grade faces
[medium|blasting_optimization ] Shorten the blast-to-mucking window while inflow is elevated
```

**2024-02**, forecast-level-led, `p = 0.991` — a different card set:
```
[high  |schedule_adjustment   ] Prioritise shaft-sinking milestones against the target
[high  |equipment_redeployment] Concentrate SDL capacity on the highest-grade faces
[high  |schedule_adjustment   ] Rebalance shift allocation toward underperforming faces
[medium|blasting_optimization ] Increase advance per round on main development
[medium|equipment_redeployment] Extend hoisting windows to match the forecast level
```

Both reach `coverage_complete: true`. The suggested months `2018-05` and
`2020-04` were unavailable: the feature table starts at 2021-04 because of the
label-contamination cut.

## Known limitations

**The same aggregate risk score is used for every mine.** There are no per-mine
forecasts — MOIL publishes no mine-level monthly production — so `mine_name`
changes only the fleet vocabulary and rule set, not the probability. A card for
Balaghat and one for Dongri Buzurg rest on the same underlying risk.

**Rules are hand-written, not learned.** `confidence` is always `rule_based`.
They encode plausible mining practice against a driver, not measured
effectiveness; nothing here has been validated against outcomes.

**Mean reversion is explained, not modelled.** The footnote tells a reader why
a healthy-looking trend can raise risk, but the engine cannot distinguish
mean reversion from a genuine deterioration — it reports what SHAP says.

**Seasonal rules are the thinnest.** `seasonal_signal` aggregates two cyclical
encodings and rarely leads; its three rules per mine type exist for coverage
and have not fired in either scenario.

**Low-risk months show an empty panel.** Correct behaviour, but it means the
live endpoint alone does not demonstrate the engine — the scenario endpoint
exists for that.

## Tests

**44 tests** in `tests/test_recommendations.py`, covering risk bands, the
positive-SHAP ranking principle, mine-type vocabulary, the equipment-vocabulary
guard across all 32 templates, `limit` and diversity-preserving truncation, the
counterintuitive detector parametrised across all nine features, footnote
deduplication and suppression, both endpoints, and validation.

Full suite: **238 passed, 1 skipped**. The skip remains
`test_lstm_residual_reduces_error` — Phase 3.2e was deferred and never built.
