# Known Issues

Recorded, not fixed. Phase 2 is frozen for the hackathon; these are
post-hackathon work. Each entry carries the evidence that found it so nobody
has to re-derive it.

---

## 1. `POST /predict/points_in_bbox` (formerly `/predict/bbox`) returns a non-griddable, out-of-bounds point set

**Severity:** medium — blocks map rendering, routed around rather than fixed.
**Found:** 2026-09-09, during the Phase 4 endpoint audit.
**Status:** open. `GET /prospectivity/heatmap` exists specifically because of
this and does not share the code path.
**Renamed 2026-09-13** to `/predict/points_in_bbox`, so the name no longer
implies a grid. `/predict/bbox` still works as a deprecated alias with the
header `X-Deprecated: use-predict-points-in-bbox`. The behaviour below is
unchanged.

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
(That 24.5% was measured on the wrong serving mosaic, known issue #7. On the
corrected mosaic it is 23.9–43.9% depending on viewport; see
`docs/frontend_heatmap_guidance.md`.)

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
**Status:** **RESOLVED 2026-09-13.**
- **Coordinates:** the Nagpur mines' coordinates were corrected from cited
  sources (#8). Kandri (21.4125, 79.2667) and Beldongri (21.3495, 79.3003) sit
  well inside the mosaic, not south of it.
- **Gumgaon:** at (21.400, 78.980) it was 0.9 km west of the mosaic's edge.
  It is now covered by a western Sentinel-2 + DEM strip in the serving
  rasters, and scores 0.9713.
- **Check:** `scripts/diagnostics/verify_all_mines_scoreable.py` scores all
  ten mines with real imagery.

The evidence below describes the *old* coordinates and footprint.

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

### Update 2026-09-13 — the DEM is not the binding constraint

A proposed fix was to extend the DEM south to lat 20.9. Checked before
building it: **extending the DEM alone would make none of the three mines
scoreable**, because Sentinel-2 imagery is missing there too.

| raster covering the mines | valid pixels within 1 km of any of the three mines |
|---|---|
| `s2_nagpur_smoke_test.tif` (primary mosaic) | 0% at the mine points (18% of Beldongri's neighbourhood) |
| `unlabelled/Nagpur_1.tif` (national fallback, lat 20.996–21.304) | **0%**; the tile is 0.2% valid overall |
| Copernicus GLO-30 DEM | available (tiles `N20/N21 × E078–E080` on Earth Search) |

Scoring the mines would need a new Sentinel-2 composite for the southern
strip. Earth Search lists 121 L2A scenes under 20% cloud over
`[78.9, 20.9, 80.6, 21.31]` for the Sausar mosaic's 2024-11 to 2025-02 window,
so it is obtainable. It is an imagery acquisition, though, not a DEM tweak.

Mine coordinates also disagree by ~25 km. `settings.MOIL_MINES` has Gumgaon
`(21.2333, 78.9333)`, Kandri `(21.2667, 79.0000)` and Beldongri
`(21.2833, 79.0500)`. A second set in circulation, `(21.02, 79.06)`,
`(21.11, 79.07)` and `(21.16, 79.09)`, falls in and around Nagpur city. Neither
set is source-cited; resolve which is right before acquiring imagery for them.
Gumgaon's `settings` coordinate also sits 0.003° west of `Nagpur_1.tif`.

See also #6: at these locations the API currently returns a score computed
from a blank patch, not a no-data response.

---

## 6. Blank tile patches are scored instead of reported as no data

**Severity:** medium — produces confident-looking numbers with no imagery behind them.
**Found:** 2026-09-13, while investigating the DEM extension above.
**Status:** **RESOLVED 2026-09-13.** `has_imagery()` in `predict.py` requires
all six bands to be non-null and non-zero. Without that, `/predict/point`
returns `404 no_imagery_at_location`, `/predict/points_in_bbox` drops the
point, and `/prospectivity/heatmap` returns `null`. The national-tile fallback
only accepts a tile with real pixels at the point.
`tests/test_serving_imagery.py` covers all three. The evidence below is kept
as the record of what was wrong.

### Evidence

`build_feature_frame` falls back to a national tile for points outside the
Sausar mosaic. `Nagpur_1.tif` covers the three southern mines by extent but
holds zeros (nodata) there. What happens next:

1. band sampling returns nodata, so all 14 base features are null
2. `read_patch` still returns a patch of zeros, because the point is inside
   the tile's bounds
3. the autoencoder embeds that blank patch; `ae_00 = 0.1717` at every such
   point, so the 64 AE columns are not null
4. `predict_point` treats non-null AE columns as "inside the footprint" and
   scores the point

Result: **Kandri and Beldongri return `0.0009`** from `/predict/point`, with
`features_extracted` entirely null, at both coordinate sets. The heatmap uses
the same "AE not null" test. In the `[78.85, 21.15, 79.30, 21.45]` 8×8 test
viewport, 44 of 64 cells have no band data, yet 40 cells are scored, so about
20 cells are blank-patch scores.

### Consequences

- Issue #2's resolution ("v6 scores null-feature points at 0.001") is v6
  scoring a blank-patch embedding low. It is not the absence of data being
  handled.
- Contract section 10 promises `null` for cells whose features are all null;
  outside the mosaic the code does not deliver that.
- The three warm viewports are unaffected: every one of their 3,072 cells has
  real band data.

### Suggested fix

Treat a point as usable only when its band features are non-null, not merely
its AE columns. `/predict/point` would return `404` and the heatmap `null` at
these locations. `test_v6_promotion_ordering` pins the current behaviour and
would need its second half changed to expect no score.

---

## 7. The API scored from a different mosaic than v6 was trained on

**Severity:** high — changed scores at every location and fabricated a quarter of the demo heatmap.
**Found:** 2026-09-13, while checking imagery at revised mine coordinates.
**Status:** **RESOLVED 2026-09-13.** Serving now reads
`s2_moil_operational_v1.tif`, which is the training mosaic byte-for-byte plus a
western strip.

### What was wrong

v6's training code reads `s2_sausar_v2.tif`
(`train_pu_xgboost_v5.py`, `SAUSAR_V2`). `predict.py` defaulted
`ACTIVE_S2_PATH` to `None`, which fell through to
`settings.s2_smoke_test` = `s2_nagpur_smoke_test.tif`. The
`PROSPECTIVITY_S2` override that would have fixed it was never set when v6
was promoted.

The two mosaics share one 20 m grid but are different composites:

| | `s2_sausar_v2.tif` (training) | `s2_nagpur_smoke_test.tif` (was served) |
|---|---|---|
| composite window | 2024-09 to 2025-04, cloud < 35%, 6 scenes/tile | 2024-11 to 2025-02, cloud < 20%, 3 scenes/tile |
| valid pixels | 100% | 74.3% |
| nodata declared | `0` | none, so gaps read as reflectance `0` |

### Evidence

Warm viewports, `grid_size=32`, cells whose six bands were all zero in the
served mosaic:

| viewport | blank cells | their median score | their share ≥ 0.90 |
|---|---|---|---|
| `full_bbox` | 268 / 1024 | 0.80 | 34.3% |
| `balaghat_bhandara` | 225 / 1024 | 0.86 | 44.9% |
| `balaghat_ukwa` | 0 / 1024 | — | — |

The blank cells formed one block in the north-west of each viewport and
scored *higher* than real cells, so the demo map's brightest region was
partly fabricated.

Scores at the same coordinates, before and after the switch:

| point | smoke mosaic | training mosaic |
|---|---|---|
| Ukwa (21.9667, 80.4667) | 0.366 | 0.99 |
| Balaghat (21.8333, 80.2333) | 0.186 | 0.335 |
| Sitapatore mining-plan point (21.70, 79.6667) | 0.566 (a gap) | 0.116 |

### Resolution

- `settings.S2_SERVING_PATH` / `DEM_SERVING_PATH` name the serving rasters,
  and `predict.py` defaults to them. `PROSPECTIVITY_S2` / `PROSPECTIVITY_DEM`
  still override.
- `has_imagery()` treats any null or zero band as no imagery (known issue #6),
  so a future raster without declared nodata cannot repeat this.
- The heatmap cache key now includes the imagery file names as well as the
  model version.
- `tests/test_serving_imagery.py` pins the serving path and asserts that the
  training mosaic's pixels are served unchanged.

---

## 8. Mine coordinates have uneven confidence, and six lack a full source URL

**Severity:** low — every mine is scoreable, but map markers are not equally precise.
**Found:** 2026-09-13, during coordinate reconciliation.
**Status:** open, documented. Coordinates in `settings.MOIL_MINES`; provenance
in `docs/moil_coordinate_sources.md`.

| mine | confidence | why |
|---|---|---|
| Balaghat, Ukwa, Chikla, Gumgaon, Kandri | high | regulatory boundary centroid or stated point |
| Sitapatore | high | MOIL Mining Plan on forestsclearance.nic.in; a stated location, not a lease boundary |
| Munsar | medium_high | PFR stated center of two lease blocks |
| Dongri Buzurg | low_medium | Wikipedia railway-station proxy, ~1–2 km from the mine |
| Tirodi | low_medium | Wikipedia town-centroid proxy, ~1–3 km from the mine |
| Beldongri | low | USGS MRDS via a third-party site |

**No full source URL** for Balaghat, Chikla, Gumgaon, Kandri, Munsar and
Beldongri: the submitted links were truncated, so `source_url` is `null`. The
source document also lacks access dates, document IDs and page references
for every mine.

**Types not verified:** the submission listed Tirodi and Dongri Buzurg as
underground on proxy sources only. Both stay opencast, per
`src/reference/moil_mines.py`.

**The corrected coordinates move the flagship scores.** The v6 promotion
evidence (`docs/phase_4/v6_promotion_verification.md`) was measured at the old
coordinates, which still score 0.99 on the training mosaic. At the corrected
points Balaghat scores 0.3352 and Dongri Buzurg 0.3271. The promotion test
keeps the historical points because it pins model behaviour; a demo that
cites "flagship mines score at the cap" should not use the corrected markers
as its evidence.

**Resolution path:** full URLs and document IDs from the coordinate
researcher; MOIL mining plans filed with IBM, or an RTI request, for
boundary-precision coordinates.

---

## 9. Concurrent first import of shap crashed matplotlib

**Severity:** medium — intermittent 500s right after startup.
**Found:** 2026-09-13, as an order-dependent failure of
`test_heatmap_shape_matches_contract` in the full suite (it passed alone).
**Status:** **RESOLVED 2026-09-13.**

`import shap` takes ~4 s and imports IPython and `matplotlib.pyplot` along
the way. The cache-warming thread imports it lazily (`/shortfall/risk`), and
so does the request path (`predict` → `explain`). When the two overlapped,
`pyplot` found IPython partially initialised in `sys.modules` and raised
`AttributeError: partially initialized module 'IPython' has no attribute
'get_ipython'`. Any request in the first few seconds after startup could hit
it; the extra `TestClient` in `tests/test_mine_coordinates.py` made it
visible in the suite.

**Fix:** the lifespan handler imports `src.models.prospectivity.explain`
(which selects the Agg backend, then imports pyplot and shap) on the main
thread before starting the warming thread. Startup is ~4 s longer; the race
is gone. `test_shap_is_fully_imported_before_warming_starts` pins it.
