# Manganese Prospectivity Mapping

SIH 2026 project (SIH26009) - Ministry of Steel / MOIL Limited.

Predicts manganese ore prospectivity, forecasts production shortfalls,
and recommends corrective actions using satellite imagery, MOIL public
disclosures, and IMD weather data.

## Data

- **India** (`data/raw/india/`): 46 real boreholes + 490 NGDR national
  records + surface XRF samples + block-level grade priors.
- **Foreign** (`data/raw/foreign/`): 1,333 analogue deposits from
  Geoscience Australia + USGS. Used for pretraining.

## Structure

- `data/` - raw + processed datasets (gitignored)
- `notebooks/` - exploratory analysis + smoke tests
- `src/` - production pipeline code
- `tests/` - unit tests

## Setup

```bash
pip install -r requirements.txt
python src/data/smoke_test.py
jupyter notebook notebooks/02_smoke_test.ipynb
```
