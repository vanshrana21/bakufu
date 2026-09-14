"""
Create the Phase 3 forecasting tables.

  moil_monthly_production   MOIL company-wide monthly output
  imd_rainfall_daily        daily rainfall for the MOIL districts
  production_forecasts      one row per (forecast_date, target_period)
  shortfall_risks           monthly shortfall risk score + factors

Uses SQLAlchemy metadata so the DDL always matches src/db/models.py.
Idempotent: checkfirst=True, so existing tables are left alone.
"""

from sqlalchemy import inspect, text

from src.db.models import (
    ImdRainfallDaily,
    MoilMonthlyProduction,
    ProductionForecast,
    ShortfallRisk,
)
from src.db.session import get_engine

NEW_TABLES = (MoilMonthlyProduction, ImdRainfallDaily, ProductionForecast, ShortfallRisk)


def migrate() -> None:
    engine = get_engine()
    for model in NEW_TABLES:
        model.__table__.create(bind=engine, checkfirst=True)
        print(f"  ensured {model.__tablename__}")

    inspector = inspect(engine)
    print("")
    print("  row counts:")
    with engine.connect() as conn:
        for model in NEW_TABLES:
            name = model.__tablename__
            if name not in inspector.get_table_names():
                print(f"    {name:<26} MISSING")
                continue
            count = conn.execute(text(f"SELECT COUNT(*) FROM {name}")).scalar()
            print(f"    {name:<26} {count}")


if __name__ == "__main__":
    migrate()
