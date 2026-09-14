# BAKUFU

Mineral intelligence prototype for Smart India Hackathon problem statement **SIH26009** (Ministry of Steel, MOIL manganese). It screens historic waste and slag dumps as candidate "Ghost Reserves" and pairs that with production forecasting and shortfall risk.

Independent hackathon prototype. No official endorsement. Demonstration data, simulated workflows and model limitations are labelled in every module.

## What's in this repo

| Folder | What it is |
|---|---|
| `frontend/` | Next.js 14 app: the BAKUFU story landing page and the ten-room workspace (operations, explorer, production, actions, assets, feedback, pipeline, compliance, reports, admin). |
| `backend/` | FastAPI service: production forecast, shortfall risk, prospectivity heatmap, point and area predictions, recommendations. |

## Run it locally

### 1. Backend: http://127.0.0.1:8000

Needs Python 3.11. The trained models and processed data are not in git; they come from a separate artifact bundle (about 311 MB). [`backend/BOOTSTRAP.md`](backend/BOOTSTRAP.md) has the full walkthrough.

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
curl -L -o moil_artifacts_bundle.tar.gz \
  https://github.com/yashnimde-ship-it/Spin-off/releases/download/v0.2-artifacts/moil_artifacts_bundle.tar.gz
tar -xzf moil_artifacts_bundle.tar.gz
cp .env.example .env   # optional: DATABASE_URL enables /shortfall/risk, /priors, /boreholes, /foreign
python scripts/run_api.py
```

### 2. Frontend: http://localhost:3000

Needs Node 18.17 or newer.

```bash
cd frontend
npm ci
cp .env.example .env.local   # uncomment NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000 for live data
npm run dev
```

With `NEXT_PUBLIC_API_BASE_URL` left unset, every screen runs on clearly labelled demonstration fixtures, so the frontend works without the backend.

More detail: [`frontend/README.md`](frontend/README.md) and [`backend/BOOTSTRAP.md`](backend/BOOTSTRAP.md).
