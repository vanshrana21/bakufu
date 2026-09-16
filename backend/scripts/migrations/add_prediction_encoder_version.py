"""
Record which encoder scored each stored prediction.

  encoder_version  fingerprint of the autoencoder weights used for this row

A stored prediction already carried its model version, which is not enough to
reproduce it: the autoencoder defines 64 of the model's input features, so the
same bundle scored under a different encoder is a different result. Without this
column an audit row cannot say which one it was.

Nullable on purpose. Rows written before this column existed genuinely do not
know their encoder, and backfilling them with today's fingerprint would state
something nobody verified.

Idempotent: safe to re-run.
"""

from sqlalchemy import text

from src.db.session import get_engine

COLUMNS = (("encoder_version", "VARCHAR(64)"),)


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
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_name = 'predictions'
                ORDER BY ordinal_position
                """
            )
        ).all()
        print("")
        print("  predictions columns now:")
        for name, data_type, nullable in rows:
            print(f"    {name:<24} {data_type:<20} null={nullable}")


def verify() -> bool:
    """True when every column this migration adds is present."""
    engine = get_engine()
    with engine.connect() as conn:
        present = {
            row[0]
            for row in conn.execute(
                text("SELECT column_name FROM information_schema.columns WHERE table_name = 'predictions'")
            )
        }
    missing = [name for name, _ in COLUMNS if name not in present]
    for name in missing:
        print(f"  MISSING predictions.{name}")
    return not missing


if __name__ == "__main__":
    migrate()
