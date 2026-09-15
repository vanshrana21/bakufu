"""
Bring an existing database up to src/db/models.py for background jobs and
prediction lookups.

  background_jobs                persistent state for POST /train
  predictions.mask_applied etc.  re-ensured, for databases older than
                                 add_prediction_mask_cols.py
  ix_predictions_model_version   index=True on Prediction.model_version
  ix_predictions_created_at      index=True on Prediction.created_at

A fresh database gets all of this from `python -m src.db.init_db`; this script
is for one that already exists. Idempotent: safe to re-run.

Run from backend/:  python -m scripts.migrations.add_background_jobs
"""

from sqlalchemy import inspect, text

from src.db.models import BackgroundJob
from src.db.session import get_engine

PREDICTION_COLUMNS = (
    ("mask_applied", "VARCHAR(50)"),
    ("raw_score", "DOUBLE PRECISION"),
    ("final_score", "DOUBLE PRECISION"),
)

#: Names match SQLAlchemy's ix_<table>_<column> convention for index=True, so
#: the live schema and the model metadata describe the same objects.
PREDICTION_INDEXES = (
    ("ix_predictions_model_version", "model_version"),
    ("ix_predictions_created_at", "created_at"),
)


def migrate() -> None:
    engine = get_engine()

    BackgroundJob.__table__.create(bind=engine, checkfirst=True)
    print("  ensured background_jobs")

    with engine.begin() as conn:
        for name, sql_type in PREDICTION_COLUMNS:
            conn.execute(text(f"ALTER TABLE predictions ADD COLUMN IF NOT EXISTS {name} {sql_type};"))
            print(f"  ensured predictions.{name} {sql_type}")
        for index, column in PREDICTION_INDEXES:
            conn.execute(text(f"CREATE INDEX IF NOT EXISTS {index} ON predictions ({column});"))
            print(f"  ensured {index}")

    inspector = inspect(engine)
    print("")
    print("  background_jobs columns:", [c["name"] for c in inspector.get_columns("background_jobs")])
    print("  predictions indexes:", sorted(i["name"] for i in inspector.get_indexes("predictions")))


if __name__ == "__main__":
    migrate()
