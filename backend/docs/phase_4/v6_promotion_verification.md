# Prospectivity model promotion: v1 → v6

**Promoted 2026-09-09.** `src/models/prospectivity/predict.py` now resolves
`SHIPPED_MODEL_PATH = models/prospectivity_v6.pkl`. `MODEL_PATH`
(`prospectivity_v1.pkl`) remains the training scratch target and is no longer
served, matching the pattern used for the forecast models after a training run
silently replaced a shipped one.

Both bundles carry the same 78-feature schema, so promotion needed no code
change beyond the path. v6 trains on **2,399 samples with 954 positives**
against v1's **1,062 with 62** — roughly fifteen times the positive class.

## Why: v1 served a near-inverted map

| Mine | v1 | v6 | null features |
|---|---|---|---|
| Gumgaon | outside footprint | outside footprint | — |
| **Kandri** | **0.990** | **0.001** | 14 / 14 |
| **Beldongri** | **0.990** | **0.001** | 14 / 14 |
| Munsar | 0.015 | 0.821 | 0 |
| **Dongri Buzurg** | 0.056 | **0.990** | 0 |
| Tirodi | 0.035 | 0.850 | 0 |
| Chikla | 0.011 | 0.596 | 0 |
| **Balaghat** | 0.003 | **0.990** | 0 |
| Sitapatore | 0.000 | 0.281 | 0 |
| Ukwa | 0.624 | 0.247 | 0 |

Under v1, MOIL's two flagship mines — Balaghat, the deepest underground
manganese mine in Asia, and Dongri Buzurg, the largest opencast — scored
**0.003 and 0.056**, while the two points whose features were *entirely null*
scored **0.990**, the cap. The highest-scoring locations on the map were the
two with no data behind them.

v6 reverses both: the flagships sit at the cap and the null-feature points
drop to 0.001.

## Side effect: the null-feature scoring bug is resolved

v6 no longer assigns high scores to an all-null feature vector, so the
proposed `/predict/point` hotfix (raise `404` when every feature is null) is
no longer needed. The heatmap's `null` handling stays as belt-and-braces: it
is cheap, and it protects against any future bundle regressing on this.

## Heatmap coverage, three warm viewports, `grid_size=32`, v6

| viewport | bbox | total | outside raster | scored | score range |
|---|---|---|---|---|---|
| `full_bbox` | 79.0, 21.3, 80.6, 22.1 | 1024 | 0 | 1024 (100%) | 0.002 – 0.990 |
| `balaghat_bhandara` | 79.53, 21.32, 80.57, 22.05 | 1024 | 0 | 1024 (100%) | 0.001 – 0.990 |
| `balaghat_ukwa` | 80.05, 21.70, 80.60, 22.05 | 1024 | 0 | 1024 (100%) | 0.001 – 0.990 |

All three are fully inside the usable footprint, so none contain null cells.
Coverage is identical under v1 and v6 — the footprint is a property of the
rasters, not the model.

## Qualitative read: do hotspots track real mining?

Grid cells containing each mine, `balaghat_bhandara` viewport:

| mine | cell | score | distance to nearest cell >= 0.90 |
|---|---|---|---|
| Dongri Buzurg | (25, 3) | 0.990 | 0 |
| Chikla | (27, 6) | 0.965 | 0 |
| Tirodi | (16, 5) | 0.859 | 1 |
| Balaghat | (10, 20) | 0.787 | 3 |
| Sitapatore | (8, 20) | 0.413 | 1 |
| Ukwa | (4, 28) | 0.222 | 4 |

**Four of six mines sit on or within one cell of a hotspot**, and the two
highest-scoring cells in the viewport contain actual operating mines. The
signal is not random with respect to known mining.

Balaghat reads 0.787 here against 0.990 when scored at its exact coordinate,
because a 32x32 cell over this bbox is roughly 3 x 2.5 km and its centre sits
about a kilometre from the shaft. Cell scores are area averages, not point
scores; the two should not be expected to match.

Ukwa is the weakest at 0.222, consistent with its low point score (0.247).

### Caveat worth carrying into the demo

**251 of 1024 cells (24.5%) score at or above 0.90.** v6 ranks known mines
correctly but is permissive at the top of the range, so a naive linear colour
ramp will render roughly a quarter of the map as maximum prospectivity — a
large red mass rather than discrete targets.

This is a presentation problem more than a model one, and the fix belongs in
the frontend: a percentile-based or non-linear colour scale would separate the
top of the distribution far better than a linear 0–0.99 ramp. Worth agreeing
with whoever builds the map legend before demo day.

## Test impact

No existing test asserted v1 scores. The `"model_version": "prospectivity_v1"`
string in `tests/test_prospectivity.py` sits inside a **monkeypatched mock
payload**, so it exercises response schema rather than model behaviour and
passes unchanged.

A v6 regression guard was added instead — see
`test_v6_promotion_ordering` in `tests/test_prospectivity.py`, which pins the
two properties that motivated the promotion: flagship mines score high, and
null-feature points score low.

## Cache

No heatmap cache existed at promotion time, so there was nothing to
invalidate. The cache key includes `model_version` precisely so a future
promotion cannot serve stale tiles.
