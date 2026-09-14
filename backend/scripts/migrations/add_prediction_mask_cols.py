"""
Add mask bookkeeping columns to the predictions table.

  mask_applied  which post-filter produced final_score
  raw_score     score before masking (so a masked-out cell stays inspectable)
  final_score   score after masking and capping

Idempotent: safe to re-run.
"""

from sqlalchemy import text

from src.db.session import get_engine

COLUMNS = (
    ("mask_applied", "VARCHAR(50)"),
    ("raw_score", "DOUBLE PRECISION"),
    ("final_score", "DOUBLE PRECISION"),
)


def migrate() -> None:
    engine = get_engine()
    with engine.begin() as conn:
        for name, sql_type in COLUMNS:
            conn.execute(
                text(f"ALTER TABLE predictions ADD COLUMN IF NOT EXISTS {name} {sql_type};")
            )
            print(f"  ensured predictions.{name} {sql_type}")

        rows = conn.execute(
            text(
                """
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_name = 'predictions'
                ORDER BY ordinal_position
                """
            )
        ).all()
        print("")
        print("  predictions columns now:")
        for name, data_type in rows:
            print(f"    {name:<24} {data_type}")


if __name__ == "__main__":
    migrate()
