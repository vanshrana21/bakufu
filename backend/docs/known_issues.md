# Known Issues

Recorded, not fixed. Phase 2 is frozen for the hackathon; these are
post-hackathon work. Each entry carries the evidence that found it so nobody
has to re-derive it.

---

## 1. `POST /predict/bbox` returns a non-griddable, out-of-bounds point set

**Severity:** medium — blocks map rendering, routed around rather than fixed.
**Found:** 2026-09-09, during the Phase 4 endpoint audit.
**Status:** open. `GET /prospectivity/heatmap` exists specifically because of
this and does not share the code path.

### Evidence

Request: `min_lon 79.5, min_lat 21.4, max_lon 79.7, max_lat 21.6`,
`grid_resolution_m 5000` — a bbox that should yield roughly a 6x6 grid.

| observation | measured |
|---|---|
| cells returned | 36 |
| distinct longitudes | 36 |
| distinct latitudes | 36 |
| cells outside the requested bbox | **16 of 36** |
| returned extent | `79.4977, 21.4000` to `79.7411, 21.6278` |
| requested extent | `79.5, 21.4` to `79.7, 21.6` |
| ordering | sorted by score descending, not spatial |

A 6x6 lattice would have 6 distinct longitudes and 6 distinct latitudes. Every
cell having a unique pair means the points are not axis-aligned in WGS84.
Consecutive longitude steps run `0.000466, 0.000465, 0.000464, 0.000463,
0.000461, 0.045979` — a roughly hundred-fold jump, consistent with a grid
built in projected metres and reprojected per point.

### Consequences

- the response cannot be reshaped into a 2D array for a raster overlay
- 44% of returned cells lie outside the viewport the caller asked for
- array order carries no spatial meaning, so index arithmetic is unsafe

### Why it is not being fixed now

Phase 2 is frozen. Nothing currently consumes the endpoint in a way a fix
would break — it is used as a ranked list of candidate sites, which is what it
does correctly. The map view consumes `/prospectivity/heatmap` instead.

---

## 2. Null features produce a maximum prospectivity score

**Severity:** high — a credibility risk in the demo if surfaced unguarded.
**Found:** 2026-09-09, while choosing heatmap viewports.
**Status:** **RESOLVED 2026-09-09 as a side effect of promoting v6** (issue
#3). v6 no longer assigns high scores to an all-null feature vector: Kandri
and Beldongri moved from 0.990 to 0.001. The proposed `404`-on-null-features
hotfix is therefore unnecessary. The heatmap's `null` handling stays as
belt-and-braces — it is cheap, and it guards against a future bundle
regressing on this.

### Evidence

`POST /predict/point` at the ten MOIL mine coordinates:

| mine | score | null features | note |
|---|---|---|---|
| Kandri | **0.990** | **14 of 14** | score at cap, no data behind it |
| Beldongri | **0.990** | **14 of 14** | score at cap, no data behind it |
| Munsar | 0.015 | 0 of 14 | |
| Chikla | 0.011 | 0 of 14 | |
| Balaghat | 0.003 | 0 of 14 | |
| Ukwa | 0.624 | 0 of 14 | |
| Gumgaon | — | — | honest `404`, outside imagery footprint |

Kandri and Beldongri sit just outside the imagery footprint. Gumgaon, slightly
further out, correctly returns `404 (21.2333, 78.9333) falls outside the
available imagery footprint`. The boundary cases do not: they return the
maximum possible score, derived from fourteen null features.

### Consequences

An unguarded map would render its two brightest hotspots at the two locations
with no underlying data — and both are real MOIL mines, so the error would
look like a confident model finding rather than a gap.

### Workaround in place

`/prospectivity/heatmap` returns `null` for any cell whose features are all
null, keeping it visually distinct from a genuine low score of `0.0`.

### Suggested fix (post-hackathon)

Make the null-feature path behave like the out-of-footprint path: return `404`
from `/predict/point`, and exclude the cell from `/predict/bbox`, rather than
scoring a feature vector that is entirely missing.

---

## 3. The API serves `prospectivity_v1.pkl` while `v6` exists

**Severity:** medium — the demo shows a five-versions-old model.
**Found:** 2026-09-09, during the Phase 4 endpoint audit.
**Status:** **RESOLVED 2026-09-09.** v6 promoted via `SHIPPED_MODEL_PATH` in
`src/models/prospectivity/predict.py`. Full evidence and verification in
`docs/phase_4/v6_promotion_verification.md`. One caveat carried forward: v6
scores 24.5% of cells at or above 0.90, so the map legend needs a
percentile-based or non-linear colour ramp rather than a linear 0–0.99 one.

### What was wrong

`predict.py` loaded `models/prospectivity_v1.pkl` while `models/` also held
`v2` through `v6`. Every `/predict/*` response reported
`"model_version": "prospectivity_v1"`, and v1 ranked MOIL's flagship mines
near zero while scoring 0.990 on all-null feature vectors.

### Resolution

`SHIPPED_MODEL_PATH` now points at `prospectivity_v6.pkl`; `MODEL_PATH`
remains the training scratch target. No test asserted v1 scores — the
`prospectivity_v1` string in `tests/test_prospectivity.py` sits inside a
monkeypatched mock payload. `test_v6_promotion_ordering` was added to pin the
behaviour that motivated the change.

---

## 4. Prophet forecast intervals are too narrow

**Severity:** low — documented in the contract, visible to the frontend.
**Found:** Phase 3.2, during the vanilla Prophet backtest.
**Status:** accepted for the demo.

CI80 coverage runs 60.0-71.4% against a nominal 80%. MCMC sampling
(`mcmc_samples=300`) lifted coverage by roughly 12 pp over analytical
intervals but did not close the gap. `/forecast` returns `ci80_coverage` in
`accuracy_at_horizon` so the UI can state the real figure.

Options if time allows: empirically recalibrate intervals from backtest
residuals, or relabel them as 70% intervals in the demo.

---

## 5. Raster footprint does not cover three Nagpur mines

**Severity:** medium — three of ten MOIL mines cannot be scored.
**Found:** 2026-09-09, while choosing heatmap warm viewports.
**Status:** **accepted, not fixed.** This is a scope constraint of the
acquired imagery, not a defect in the code.

Raster footprint does not cover 3 Nagpur mines (Gumgaon 21.23, Kandri 21.26,
Beldongri 21.28). DEM boundary at 21.3 is the hard constraint; extending south
loses cells rather than gaining. Frontend renders mine markers outside the
heatmap raster with tooltip explaining the scope limitation.

### Evidence

| footprint | extent |
|---|---|
| Sentinel-2 (reprojected to WGS84) | lon 78.9888–80.6024, lat **21.2886**–22.1118 |
| DEM | lon 79.0000–80.6000, lat **21.3000**–22.1000 |
| usable intersection | lon 79.0000–80.6000, lat **21.3000**–22.1000 |

Feature extraction needs both rasters, so the usable southern limit is
**21.3000**. Sentinel-2 reaches 0.011° (~1.2 km) further south, but with no
elevation beneath it those cells still produce null features.

Measured at `grid_size=32`:

| bbox | cells | outside raster | scored |
|---|---|---|---|
| extended, min_lat 21.2 | 1024 | 128 | 896 (87.5%) |
| current, min_lat 21.3 | 1024 | 0 | 1024 (100%) |

Extending south is **−128 scored cells**: the four bottom rows fall entirely
below the DEM edge. Gumgaon, Kandri and Beldongri sit below even the
Sentinel-2 limit, so no viewport can show them.

### Frontend handling

Mine markers render outside the heatmap raster with the tooltip: *"This mine
lies outside the model's current imagery footprint. Prospectivity scoring is
not available for this location."* Wording to be confirmed with the frontend
owner.
