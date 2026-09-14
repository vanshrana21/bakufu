"""
Add deposit_type column to boreholes, surface_samples and ngdr_national.

foreign_deposits already carries deposit_type from the Phase 1 loader, so it
is left alone here.

Idempotent: safe to re-run.
"""

from sqlalchemy import text

from src.db.session import get_engine

TABLES = ("boreholes", "surface_samples", "ngdr_national")


def migrate() -> None:
    engine = get_engine()
    with engine.begin() as conn:
        for table in TABLES:
            conn.execute(
                text(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS deposit_type VARCHAR(20);")
            )
            print(f"  ensured {table}.deposit_type")

        print("\nCurrent nullability:")
        for table in TABLES + ("foreign_deposits",):
            total = conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()
            filled = conn.execute(
                text(f"SELECT COUNT(*) FROM {table} WHERE deposit_type IS NOT NULL")
            ).scalar()
            print(f"  {table:20s} {filled}/{total} populated")


if __name__ == "__main__":
    migrate()
