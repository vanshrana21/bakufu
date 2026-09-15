# BAKUFU 幕府

> The house that commands the ground.

Mineral intelligence for MOIL, built for Smart India Hackathon problem statement **SIH26009** (Ministry of Steel). BAKUFU screens the historical waste dumps of the Sausar Belt, India, for manganese Ghost Reserves: ore that decades of mining moved aside and never processed. It pairs that screen with a production forecast, a shortfall risk and corrective actions that wait for a human decision. A second mine, already dug.

## What it does

Four MVP features, served live from the backend:

| Feature | Route | What you get |
|---|---|---|
| Prospectivity Explorer | `/explorer` | A 32 × 32 surface over the Sausar Belt. Toggle the geological and 5 km occurrence-buffer masks, select a site, read its raw and screened scores and top-5 SHAP drivers. |
| Production forecast | `/production` | MOIL company-wide monthly output for 1 or 3 months ahead, each month with an 80% prediction interval. |
| Shortfall risk | `/operations`, `/production` | The probability that next month lands below 90% of the issued forecast, with the drivers behind it. |
| Corrective actions | `/actions` | Rule-based proposals, each with a trigger, evidence and a review status. None executes on its own. |

Six enterprise modules, running on labelled demonstration data:

- **Assets & Inventory:** mines, equipment readiness, screened Ghost Reserve material
- **Geologist Feedback:** field annotations that become reviewed training candidates
- **Data Pipeline:** source freshness, model versions, retraining evidence
- **Compliance:** permits, clearances, safety findings
- **Reports & Exports:** briefing generation
- **Administration & RBAC:** users, roles, audit trail

## Honesty doctrine

- **Masks decide.** Screening masks run after the model. A location they exclude reads 0.00. That zero is a policy result, not a model score.
- **Null is not zero.** Sandur and Bonai sit outside the validated Sausar scope, so they return nothing, not zero. Cells outside the imagery footprint stay empty on the map.
- **Raw scores survive.** The pre-mask score stays beside the screened one. Excluded cells are hatched, not erased.
- **The system recommends. People decide.** No approval, assignment or operational command is ever sent.
- **Demo says demo.** Modules without a backend carry a "Demo data" label. Unvalidated intervals and uncalibrated probabilities are labelled where they appear.

## Models

| Model | Artifact | Question it answers | Detail |
|---|---|---|---|
| PU-XGBoost prospectivity | `prospectivity_v6` | Where is manganese likely? | Positive-unlabelled XGBoost on a 78-feature schema, Elkan-Noto adjusted, capped at 0.99. LOBO AUC **0.9034**. |
| Prophet forecast | `prophet_baseline_v1.0` | How much will MOIL produce? | Trained on **123 months** of IBM MSMP bulletins (2016-01 to 2026-05). 300 MCMC samples, 80% intervals. Backtested coverage is 60–71%, so the intervals are known to be too narrow. |
| XGBoost shortfall | `shortfall_classifier_v1` | Will next month fall short? | Probability of production below 90% of the forecast, explained with SHAP. |
| Autoencoder | `autoencoder_v1` | What does the ground look like? | 64-dimension Sentinel-2 embeddings that feed the prospectivity model. |

The Explorer surface is **1,024 cells** (32 × 32), scored from local rasters and computed ahead of time at API startup.

## Architecture

```
  browser
     |
     v
+-------------------------+          +-------------------------------+
|  frontend/              |   HTTP   |  backend/                     |
|  Next.js 14   :3000     | -------> |  FastAPI      :8000           |
|  landing + workspace    |   JSON   |  forecast, risk, heatmap,     |
|  lib/api/ adapters      |          |  point scoring, actions       |
+-------------------------+          +---------------+---------------+
                                                     |
                                +--------------------+--------------------+
                                |                                         |
                                v                                         v
                  +---------------------------+             +---------------------------+
                  |  backend/models/          |             |  Supabase Postgres        |
                  |  1 prospectivity  PU-XGB  |             |  IMD rainfall, boreholes, |
                  |  2 forecast       Prophet |             |  priors, prediction log   |
                  |  3 shortfall      XGBoost |             +---------------------------+
                  |  4 embeddings     AE      |
                  +---------------------------+
```

## Quickstart

**Prerequisites:** Python 3.11+, Node 18.17+, and the model artifact bundle (models and processed data are not in git). A Supabase or Postgres `DATABASE_URL` is optional. Without it, shortfall risk degrades while the forecast, the map and point scoring still run.

### Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# models + processed data (~311 MB), see BOOTSTRAP.md
curl -L -o moil_artifacts_bundle.tar.gz \
  https://github.com/yashnimde-ship-it/Spin-off/releases/download/v0.2-artifacts/moil_artifacts_bundle.tar.gz
tar -xzf moil_artifacts_bundle.tar.gz

cp .env.example .env            # add DATABASE_URL
uvicorn src.api.main:app --host 127.0.0.1 --port 8000
```

On startup the API warms the forecasts, the shortfall model, the point model and the Explorer surfaces on a background thread.

### Frontend

```bash
cd frontend
npm i
echo "NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000" > .env.local
npm run dev
```

Open [http://localhost:3000](http://localhost:3000). Leave `NEXT_PUBLIC_API_BASE_URL` unset and every screen runs on labelled demonstration fixtures, no backend required. `NEXT_PUBLIC_*` values are read when the server starts, so restart after changing them.

## Repo structure

```
bakufu/
├── README.md
├── backend/
│   ├── src/
│   │   ├── api/           FastAPI app, routers, schemas, startup warming
│   │   ├── models/        prospectivity, forecast, shortfall, recommendations
│   │   ├── data/          ingest, preprocessing, screening masks
│   │   ├── db/            SQLAlchemy session and models
│   │   ├── config/        settings and constants
│   │   └── reference/     MOIL mine reference data
│   ├── tests/             pytest suite
│   ├── scripts/           run_api.py, migrations, diagnostics
│   ├── docs/              API contracts and phase reports
│   ├── notebooks/
│   ├── BOOTSTRAP.md       full setup and artifact bundle
│   ├── requirements.txt
│   └── .env.example
└── frontend/
    ├── app/               landing (/) and the (workspace) routes
    ├── components/        landing, explorer, operations, shell, ui, one folder per module
    ├── lib/
    │   ├── api/           typed adapters for the FastAPI contract
    │   └── contracts.ts   Zod response contracts
    ├── fixtures/          labelled demonstration data
    ├── hooks/  stores/
    ├── public/brand/      BAKUFU marks
    ├── tests/             Vitest unit and Playwright e2e
    ├── docs/  DESIGN.md  PRODUCT.md
    └── .env.example
```

## Tests

```bash
cd frontend
npm test              # Vitest unit suite
npx tsc --noEmit      # strict type check
npx next build        # production build
```

Backend: `cd backend && python -m pytest`.

## Disclaimer

BAKUFU is an independent hackathon prototype. It is not affiliated with or endorsed by MOIL Limited, the Ministry of Steel or the Government of India. Demonstration data, simulated workflows and scientific limitations are labelled in each module. Screening scores are an index for investigation, not a recovery probability, an ore quantity or an environmental clearance.
