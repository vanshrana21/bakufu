"""Create the PostGIS extension and every table in src/db/models.py.

For a fresh database. An existing one keeps its tables (create_all never alters
them); bring it up to date with the idempotent scripts in scripts/migrations/.

Run standalone with:  python -m src.db.init_db
"""

from __future__ import annotations

from sqlalchemy import inspect, text

from src.db.models import Base
from src.db.session import get_engine


def init_db(drop_first: bool = False) -> list[str]:
    """Enable PostGIS and create all tables. Returns the table names now present."""
    engine = get_engine()

    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis;"))
    print("PostGIS extension ensured.")

    existing_before = set(inspect(engine).get_table_names())

    if drop_first:
        print("Dropping existing tables ...")
        Base.metadata.drop_all(engine)
        existing_before = set()

    for table in Base.metadata.sorted_tables:
        status = "exists" if table.name in existing_before else "creating"
        print(f"  [{status:8s}] {table.name}")

    Base.metadata.create_all(engine)

    created = sorted(inspect(engine).get_table_names())
    print(f"\n{len(Base.metadata.sorted_tables)} tables ensured; DB now has: {created}")
    return created


def main() -> None:
    init_db()


if __name__ == "__main__":
    main()
