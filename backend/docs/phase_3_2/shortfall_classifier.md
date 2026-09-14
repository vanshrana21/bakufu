# Shortfall Classifier (Phase 3.2d)

Predicts the probability that a month's manganese production comes in below
90% of Prophet's forecast for that month. Output is a risk score for the
dashboard, not another point forecast.

## Headline finding: rainfall predicts the tail, not the mean

**`rainfall_lag2_mm` ranks 4th in SHAP importance and rainfall features carry
20.6% of total |SHAP| — in a model where rainfall added nothing whatsoever to
level forecasting (+0.13 pp MAPE, 95% CI ±0.44, p = 0.409).**

The two-month lag matches the physical mechanism: heavy monsoon rain floods
open pits and degrades haul roads, and the production impact lands weeks
after the rainfall itself. A level forecast smooths that delayed disruption
into its seasonal term; a deviation model can catch it.

This is the substantive result of Phase 3.2. Rainfall is uninformative about
central tendency and informative about the tail, and the lag structure that
carries the signal is the one the physical mechanism predicts. Supporting
evidence that this is not an artefact: `rainfall_concurrent_mm` ranks *last*
of nine features (0.055), so the signal is genuinely lagged rather than
contemporaneous.

| # | feature | mean abs SHAP |
|---|---------|---------------|
| 1 | prophet_forecast_level | 1.3488 |
| 2 | deviation_lag1 | 0.9772 |
| 3 | production_trend_3mo | 0.7709 |
| **4** | **rainfall_lag2_mm** | **0.7082** |
| 5 | deviation_lag2 | 0.3867 |
| 6 | rainfall_lag1_mm | 0.2136 |
| 7 | month_sin | 0.1751 |
| 8 | month_cos | 0.1100 |
| 9 | rainfall_concurrent_mm | 0.0553 |

Prophet-deviation features carry 28.7% of |SHAP|, so recent under-performance
is the largest single signal — but it is not doing all the work.

## Label definition and the contamination we removed

A month is labelled a shortfall when actual production falls below 90% of
Prophet's **rolling-origin** forecast for it. Every label comes from a model
fitted only on months before the one it scores; an in-sample fit would have
already seen the answer.

Prophet's rolling-origin forecasts are less accurate on early origins with
short training windows. This inflates the "shortfall" label rate during 2018
(54.5%) versus mature-model periods (17.1%), because a young Prophet
over-predicts and creates artifactual shortfalls. Training on all 98 months
would teach the classifier to detect Prophet immaturity rather than
production weakness. We restrict labels to origins with n_train >= 60
(roughly 2020-09 onward), which cleans the label and matches the deployment
condition where the model is always mature.

| set | months | positives | base rate |
|-----|--------|-----------|-----------|
| all origins | 98 | 27 | 27.6% |
| n_train >= 60 (used) | 60 | 13 | 21.7% |

## Features

All nine are causally available when the prediction is made. Prophet
deviations and production trajectory are strictly lagged. Rainfall is
published near-real-time by IMD, so the concurrent month is legitimately
known — it is named `rainfall_concurrent_mm` so the exception is visible
rather than buried.

Every row carries a `rainfall_source` column recording observed vs imputed.
In Phase 3.2c a missing provenance column let a regressor silently fall back
to climatology and produce a null result that looked real; the column exists
so that cannot recur. **In this run 0 of 60 rows were imputed** — all
rainfall was observed.

## Backtest

Walk-forward over stratified windows, training only on earlier months. Plain
equal-width windows left holdouts with no positives at all, where F1 is
undefined; stratification guarantees each window carries at least one.

| window | months | positives | span |
|--------|--------|-----------|------|
| rows 20-43 | 23 | 3 | 2022-12 .. 2024-12 |
| rows 43-46 | 3 | 2 | 2025-01 .. 2025-03 |
| rows 46-60 | 14 | 2 | 2025-04 .. 2026-05 |

**Structural limitation, reported rather than smoothed over:** three windows,
not the five intended, and badly unbalanced — the middle one is three months
long. With 13 positives and a 20-month minimum training set, only 7 positives
are available for holdout at all, so five windows of two positives each was
arithmetically impossible. Per-window F1 would be meaningless at these sizes;
only the pooled figures below are quoted.

## Results

Counts first: with 7 positives in the pooled holdout, ratios are unstable
and raw counts are the honest unit.

| model | TP | FP | TN | FN | F1 | precision | recall |
|-------|----|----|----|----|----|-----------|--------|
| **classifier** | **5** | 10 | 23 | **2** | **0.455** | 0.333 | 0.714 |
| majority-class | 0 | 0 | 33 | 7 | 0.000 | 0.000 | 0.000 |
| persistence-1lag | 2 | 5 | 28 | 5 | 0.286 | 0.286 | 0.286 |
| persistence-2lag | 3 | 10 | 23 | 4 | 0.300 | 0.231 | 0.429 |

**ROC-AUC 0.749, PR-AUC 0.344 against a 0.175 base rate** — roughly 2x lift.
These are the numbers to trust ahead of F1: they use the full probability
ranking rather than a single 0.5 threshold, so they are far less fragile to
one prediction flipping when only 7 positives exist.

The comparison against `persistence-2lag` is the cleanest read of what the
model adds: **at an identical false-alarm count (10), the classifier catches
5 real shortfalls where the simple rule catches 3.**

### On the controls

The first control we ran flagged months where Prophet *predicted* a drop
relative to trailing output. It scored F1 0.000 with zero true positives —
because it measures a different quantity from the label (Prophet predicting
low, versus actual undershooting Prophet), so it is close to orthogonal by
construction. Beating it proved nothing, and it was replaced. The persistence
rules above operate on the same deviation quantity the label is built from,
and are what a competent analyst would try before reaching for XGBoost.

## Ship decision: SHIP

All four pre-registered conditions hold.

| condition | required | actual |
|-----------|----------|--------|
| F1 over majority-class | >= +0.05 | **+0.455** |
| F1 over persistence-1lag | >= +0.03 | **+0.169** |
| F1 over persistence-2lag | >= +0.03 | **+0.155** |
| true positives detected | >= 5 | **5** |

Precision 0.333 means two false alarms per catch. For a dashboard screening
tool that is a reasonable trade — recall 0.714 means most real shortfalls are
flagged, and a false alarm costs attention rather than money. It should be
presented as a screen, not a prediction.

## Scope limitations

- **COVID-scale shocks are absent from the training data.** The n_train >= 60
  cut begins at 2021-02, so 2020-03..07 — the largest shortfalls in the
  series, including a month at 17% of median — fall outside it entirely. The
  classifier's behaviour on shocks of that magnitude is untested. This is a
  limit of scope, not a defect.
- **Seven positives in the pooled holdout.** Single prediction flips move F1
  by roughly 0.05, which is why counts and AUC are quoted alongside it.
- **The model is a screen on an aggregate.** MH+MP is a proxy for MOIL's
  operating region, not MOIL itself; a shortfall flag is a regional signal.

## Artifacts

- `src/models/shortfall_classifier.py`
- `models/shortfall_classifier_v1.pkl`
- `data/processed/shortfall_labels.parquet`, `shortfall_features.parquet`,
  `shortfall_backtest.parquet`, `shortfall_shap.png`
- MLflow run `shortfall_classifier_v1` in `phase_3_2_forecasting`
- `tests/test_shortfall.py` (9 tests)
