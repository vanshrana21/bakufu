# Bootstrap

How to get this repository running from a clean clone.

The trained models and processed data are **not in git** — they are binary
artifacts excluded by `.gitignore`. They ship as a separate bundle, described
below. Without them the API starts but every model-backed endpoint returns
`500 model_not_loaded` naming the file it wanted.

## Requirements

- **Python 3.11** (the project is developed and tested on 3.11)
- **pip** (or `uv`, if you prefer — see below)
- **Tesseract OCR 5.x** — *only* needed if you re-run the MSMP OCR recovery
  step. The five OCR-recovered months are already baked into
  `msmp_mn_monthly_wide.parquet` in the artifact bundle, so a normal setup
  does not need Tesseract. If you do want it:
  Windows installer puts it at `%LOCALAPPDATA%\Programs\Tesseract-OCR`;
  `src/data/preprocess/ocr_msmp_scanned.py` addresses the binary directly
  rather than relying on `PATH`.

## 1. Install dependencies

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows
# source .venv/bin/activate       # macOS / Linux
pip install -r requirements.txt
```

With `uv` instead:

```bash
uv venv
uv pip install -r requirements.txt
```

Prophet compiles a Stan model on first import, so the initial install is slow.

## 2. Get the artifact bundle

Download the bundle and extract it at the repo root. This populates
`models/`, `data/processed/` and the parts of `data/raw/` the API reads.

```bash
curl -L -o moil_artifacts_bundle.tar.gz \
  https://github.com/yashnimde-ship-it/Spin-off/releases/download/v0.2-artifacts/moil_artifacts_bundle.tar.gz
tar -xzf moil_artifacts_bundle.tar.gz
```

It is **~311 MB** and holds **16 files**. Most of that is the two rasters;
everything else together is under 3 MB. **Every file is required** — the API
needs all of them to serve a fully working set of endpoints. Do not trim the
bundle.

| path | what it is |
|---|---|
| `models/prophet_baseline_v1_0_shipped.pkl` | promoted production forecast model |
| `models/shortfall_classifier_v1.pkl` | shortfall risk classifier |
| `models/prospectivity_v6.pkl` | promoted prospectivity model |
| `models/autoencoder_v1.pt` | encoder for the 64 AE feature columns |
| `data/processed/prophet_metrics_baseline_v1_0.json` | shipped backtest metrics |
| `data/processed/prophet_backtest_rows_baseline_v1_0.parquet` | 82 backtest origins |
| `data/processed/msmp_mn_monthly_wide.parquet` | the 123-month production series |
| `data/processed/msmp_mn_monthly_long.parquet` | same series, long format |
| `data/processed/shortfall_features.parquet` | classifier feature table |
| `data/processed/shortfall_labels.parquet` | rolling-origin shortfall labels |
| `data/processed/moil_monthly_series.parquet` | 20 MOIL months, proxy validation only |
| `data/raw/moil/msmp_archive_full.csv` | source-of-truth list of 134 IBM bulletins |
| `data/raw/india/geology/sausar_precambrian_formations_macrostrat_proxy.geojson` | geological mask |
| `data/raw/india/geology/occurrence_buffer_5km.geojson` | occurrence-buffer mask |
| `data/raw/satellite/s2_nagpur_smoke_test.tif` | Sentinel-2 mosaic (258 MB) |
| `data/raw/dem/dem_nagpur_smoke_test.tif` | DEM tile (51 MB) |

Grouped by what breaks without them:

**Model pickles and weights (`models/`)** — 4 files:
`prophet_baseline_v1_0_shipped.pkl`, `shortfall_classifier_v1.pkl`,
`prospectivity_v6.pkl`, `autoencoder_v1.pt`.
The autoencoder is easy to overlook because it is `.pt` rather than `.pkl`,
but `predict.py` needs it for the 64 AE feature columns — without it every
`/predict/*` and `/prospectivity/heatmap` call fails.

**Processed data (`data/processed/`)** — 6 files:
`prophet_metrics_baseline_v1_0.json`, `prophet_backtest_rows_baseline_v1_0.parquet`,
`msmp_mn_monthly_wide.parquet`, `msmp_mn_monthly_long.parquet`,
`shortfall_features.parquet`, `shortfall_labels.parquet`,
plus `moil_monthly_series.parquet` for proxy validation.

**Mask GeoJSONs (`data/raw/india/geology/`)** — 2 files. Without them any
call passing `?mask=geological`, `?mask=occurrence_buffer` or `?mask=both`
fails, though `?mask=none` still works.

**Source CSV (`data/raw/moil/`)** — `msmp_archive_full.csv`, the list of 134
IBM bulletins the whole production series derives from.

**Rasters (`data/raw/satellite/`, `data/raw/dem/`)** — 2 files, and the bulk
of the bundle's size. Feature extraction needs both: the Sentinel-2 mosaic
supplies the spectral bands and the DEM supplies terrain. Without them every
`/predict/point`, `/predict/bbox` and `/prospectivity/heatmap` call fails, so
the map view has nothing to render. They are included precisely because the
map is expected to work from a fresh clone.

**Not** in the bundle, because they are large and regenerable:

- the 125 MSMP PDFs (~547 MB) — `python -m src.data.ingest.download_msmp_archive`
  re-downloads them from the URLs in `msmp_archive_full.csv`
- `data/cache/` — API response caches, regenerated on demand
- the unlabelled national tiles under `data/raw/satellite/unlabelled/` — only
  needed to score points outside the Sausar mosaic

The Sentinel-2 mosaic and DEM tile **are** in the bundle. They were previously
excluded as "regenerable", but re-fetching them needs the Phase 1/2 ingest
scripts and external credentials, and without them the prospectivity map
cannot render at all — which is the main thing a fresh clone is expected to
demonstrate.

## 3. Configure the environment

```bash
cp .env.example .env
```

Then fill in the real values.

**The API does not need `DATABASE_URL` to start.** Verified: with it unset,
all six startup artifacts load, startup completes cleanly, and
`/production/history`, `/mines`, `/forecast`, `/forecast/history` and
`/prospectivity/heatmap` all return `200`.

It *is* needed for:

| endpoint | without `DATABASE_URL` |
|---|---|
| `/priors`, `/boreholes`, `/foreign` | `500` — they read Postgres directly |
| `/shortfall/risk` | `500` — it reads IMD rainfall for its features |
| `/dashboard/summary` | still `200`, but `{"shortfall": null, "degraded": ["shortfall"]}` |
| everything else | unaffected |

The shortfall dependency is indirect and easy to miss: the classifier's
features include three rainfall terms, and `load_monthly_rainfall()` queries
`imd_rainfall_daily`. Note that once `/shortfall/risk` has been answered
successfully, the result is cached to `data/cache/` for 24 hours and will keep
serving from there even if the database later becomes unreachable — so a
working demo does not prove the connection is configured.

## 4. Verify the setup

```bash
./.venv/Scripts/python.exe -m uvicorn src.api.main:app
```

Then hit `/dashboard/summary` — should return `degraded: []`.

An empty `degraded` array means every model and data artifact loaded. If a
name appears in it, that component failed; the startup log names the file.

Startup detail worth knowing: six artifacts load eagerly in about 1.5 seconds,
then a **background thread warms caches** — four forecast horizons (~3 s), the
shortfall SHAP explanation (~3 s), and three heatmap viewports (~20–24 s
each). The API answers requests immediately; the first `/prospectivity/heatmap`
call before warming finishes will take ~38 s rather than ~10 ms.

Endpoints that work immediately post-clone (no database needed):
`/production/history`, `/mines`, `/mines/{name}`, `/forecast`,
`/forecast/history`, `/prospectivity/heatmap`, and — once `/shortfall/risk`
has been answered — `/recommendations` and
`/recommendations/scenario/{month}`.

The recommendations endpoints depend on the shortfall explanation, so they
need `DATABASE_URL` for the same reason `/shortfall/risk` does: three of the
classifier's nine features are rainfall terms.

Interactive API docs: `http://127.0.0.1:8000/docs` — 25 operations.

## 5. Run the tests

```bash
pytest -q
```

Expected: **238 passed, 1 skipped**.

The single skip is `test_lstm_residual_reduces_error`. Phase 3.2e (an LSTM on
Prophet's residuals) was deliberately deferred — it had to beat
Prophet+regressors by >= 1.5 pp MAPE to ship, and was never built — so there is
no `models/lstm_residual_v1.pt` to test. That skip marks unbuilt scope, not a
failure, and is expected for the demo.

The DB-backed tests do **not** skip when `DATABASE_URL` is set; they run
against Supabase. If the database is unreachable they will fail rather than
skip.

## Known limitations

See `docs/known_issues.md` for the full list with evidence. The short version:

- three MOIL mines (Gumgaon, Kandri, Beldongri) fall outside the imagery
  footprint and cannot be scored
- forecast CI80 coverage runs 60–71% against a nominal 80%
- the forecast loses to seasonal-naive below a 12-month horizon
- `POST /predict/bbox` returns a non-griddable point set; the map uses
  `/prospectivity/heatmap` instead

## Where to start reading

- `docs/phase_4/api_contracts.md` — the API contract (v1.6), source of truth
  for the frontend
- `docs/phase_4/bucket_1_summary.md` — the 24 Bucket 1 endpoints
- `docs/phase_4/bucket_2_summary.md` — the recommendations rules engine
- `docs/phase_4/recommendations_design.md` — driver taxonomy and rule catalog
- `docs/known_issues.md` — every known defect with the evidence that found it
