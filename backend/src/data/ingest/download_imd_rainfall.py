"""
Download daily rainfall for the MOIL mining districts.

IMD's own portals (mausam.imd.gov.in, imdpune.gov.in) do not expose a
documented public API for district daily series, so this uses Open-Meteo's
historical archive, which serves ERA5 reanalysis precipitation at a point.
Free, no key, and stable enough to depend on.

Districts are represented by their headquarters coordinates; ERA5 is a ~9 km
reanalysis grid, so a point sample stands in for the district reasonably at
monthly aggregation - which is the resolution the forecast actually uses.

Run: python -m src.data.ingest.download_imd_rainfall
"""

from __future__ import annotations

import time
from datetime import date, timedelta

import pandas as pd
import requests
from sqlalchemy import text
from tqdm import tqdm

from src.db.models import ImdRainfallDaily
from src.db.session import SessionLocal, get_engine

ARCHIVE_API = "https://archive-api.open-meteo.com/v1/archive"

START_DATE = "2010-01-01"

#: (district, state, lat, lon) - MOIL's operating districts.
DISTRICTS: list[tuple[str, str, float, float]] = [
    ("Nagpur", "Maharashtra", 21.15, 79.09),
    ("Bhandara", "Maharashtra", 21.17, 79.65),
    ("Balaghat", "Madhya Pradesh", 21.80, 80.20),
    ("Chhindwara", "Madhya Pradesh", 22.06, 78.94),
]

#: IMD long-period averages (mm/yr) for a sanity check, not for storage.
EXPECTED_ANNUAL_MM = {
    "Nagpur": 1100.0,
    "Bhandara": 1250.0,
    "Balaghat": 1350.0,
    "Chhindwara": 1150.0,
}


def fetch_district(district: str, lat: float, lon: float, end: str) -> pd.DataFrame:
    """Daily precipitation series for one point."""
    response = requests.get(
        ARCHIVE_API,
        params={
            "latitude": lat,
            "longitude": lon,
            "start_date": START_DATE,
            "end_date": end,
            "daily": "precipitation_sum",
            "timezone": "Asia/Kolkata",
        },
        timeout=120,
    )
    response.raise_for_status()
    daily = response.json()["daily"]
    return pd.DataFrame(
        {
            "date": pd.to_datetime(daily["time"]).date,
            "rainfall_mm": daily["precipitation_sum"],
        }
    )


#: The ERA5 archive lags real time; asking for today returns HTTP 400.
ARCHIVE_LAG_DAYS = 7


def load() -> dict[str, object]:
    end = (date.today() - timedelta(days=ARCHIVE_LAG_DAYS)).isoformat()
    engine = get_engine()

    frames: list[pd.DataFrame] = []
    for district, state, lat, lon in tqdm(DISTRICTS, desc="districts", unit="district"):
        frame = fetch_district(district, lat, lon, end)
        frame["district"] = district
        frame["state"] = state
        frames.append(frame)
        time.sleep(1.0)  # stay well under any rate limit

    combined = pd.concat(frames, ignore_index=True)
    combined["rainfall_mm"] = pd.to_numeric(combined["rainfall_mm"], errors="coerce")
    missing_values = int(combined.rainfall_mm.isna().sum())
    combined = combined.dropna(subset=["rainfall_mm"])

    # Normal = that district's mean rainfall for that calendar day-of-year,
    # computed from the series itself. Departure is expressed monthly, where
    # it is meaningful; a daily departure against a daily normal is noise.
    combined["date"] = pd.to_datetime(combined["date"])
    combined["month"] = combined.date.dt.month
    monthly_normal = (
        combined.groupby(["district", "month"]).rainfall_mm.mean().rename("daily_normal_mm")
    )
    combined = combined.join(monthly_normal, on=["district", "month"])
    combined["departure_pct"] = (
        (combined.rainfall_mm - combined.daily_normal_mm)
        / combined.daily_normal_mm.replace(0.0, pd.NA)
        * 100.0
    )

    with engine.begin() as conn:
        conn.execute(text("TRUNCATE TABLE imd_rainfall_daily RESTART IDENTITY"))

    records = [
        {
            "date": row.date.date(),
            "district": row.district,
            "state": row.state,
            "rainfall_mm": float(row.rainfall_mm),
            "normal_rainfall_mm": None if pd.isna(row.daily_normal_mm) else float(row.daily_normal_mm),
            "departure_pct": None if pd.isna(row.departure_pct) else float(row.departure_pct),
            "source": "open_meteo_era5_archive",
        }
        for row in combined.itertuples()
    ]
    with SessionLocal() as session:
        session.bulk_insert_mappings(ImdRainfallDaily, records)
        session.commit()

    print("")
    print("=" * 66)
    print("DISTRICT RAINFALL")
    print("=" * 66)
    print(f"  records loaded : {len(records)}")
    print(f"  dropped (null) : {missing_values}")
    print(f"  date range     : {combined.date.min().date()} .. {combined.date.max().date()}")

    print("")
    print("  per district (annual mean vs IMD long-period average):")
    print("    " + "district".ljust(14) + "days".rjust(8) + "missing".rjust(9) + "mm/yr".rjust(9) + "expected".rjust(10))
    expected_days = (combined.date.max() - combined.date.min()).days + 1
    stats: dict[str, float] = {}
    for district, group in combined.groupby("district"):
        years = (group.date.max() - group.date.min()).days / 365.25
        annual = float(group.rainfall_mm.sum() / years)
        stats[str(district)] = annual
        gaps = expected_days - len(group)
        print(
            f"    {str(district):<14}{len(group):>8}{gaps:>9}{annual:>9.0f}"
            f"{EXPECTED_ANNUAL_MM.get(str(district), float('nan')):>10.0f}"
        )

    return {"records": len(records), "annual_mm": stats}


def main() -> None:
    load()


if __name__ == "__main__":
    main()
