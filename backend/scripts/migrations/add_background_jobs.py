"""
Bring an existing database up to src/db/models.py for background jobs and
prediction lookups.

  background_jobs                created, or upgraded column by column
  background_jobs.claim_fence    the fence model promotion is judged against
  uq_background_jobs_one_...     partial unique index: at most one queued or
                                 running job per task name
  predictions.mask_applied etc.  re-ensured, for databases older than
                                 add_prediction_mask_cols.py
  ix_predictions_model_version   index=True on Prediction.model_version
  ix_predictions_created_at      index=True on Prediction.created_at

Duplicate active jobs are reconciled before the unique index is created, by an
explicit rule: keep the running job with the most recent heartbeat, else the
newest queued job, and fail every other active job for that task with a message
naming the survivor. Without that, a database holding two active rows could
never take the index.

A fresh database gets all of this from `python -m src.db.init_db`; this script
is for one that already exists. Idempotent: safe to re-run.

Run from backend/:  python -m scripts.migrations.add_background_jobs
"""

from __future__ import annotations

from sqlalchemy import Engine, inspect, text

from src.db.models import BackgroundJob
from src.db.session import get_engine

ACTIVE_JOB_INDEX = "uq_background_jobs_one_active_per_task"
ACTIVE_STATUSES = ("queued", "running")

#: Column -> (postgresql type, sqlite type). Every column src/db/models.py
#: declares, so a background_jobs table from an older release is filled in
#: rather than left half-shaped.
JOB_COLUMNS: dict[str, tuple[str, str]] = {
    "task_name": ("VARCHAR(64)", "VARCHAR(64)"),
    "status": ("VARCHAR(16) DEFAULT 'queued'", "VARCHAR(16) DEFAULT 'queued'"),
    "claim_fence": ("INTEGER DEFAULT 0", "INTEGER DEFAULT 0"),
    "progress": ("DOUBLE PRECISION", "FLOAT"),
    "result_data": ("JSON", "JSON"),
    "error_message": ("TEXT", "TEXT"),
    "created_at": ("TIMESTAMPTZ DEFAULT NOW()", "DATETIME"),
    "started_at": ("TIMESTAMPTZ", "DATETIME"),
    "finished_at": ("TIMESTAMPTZ", "DATETIME"),
    "updated_at": ("TIMESTAMPTZ DEFAULT NOW()", "DATETIME"),
}

JOB_INDEXES = (
    ("ix_background_jobs_job_id", "job_id"),
    ("ix_background_jobs_status", "status"),
)

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


def _now(dialect: str) -> str:
    return "NOW()" if dialect == "postgresql" else "CURRENT_TIMESTAMP"


def _add_missing_job_columns(engine: Engine) -> list[str]:
    """Add every column the model declares that the live table is missing."""
    dialect = engine.dialect.name
    present = {column["name"] for column in inspect(engine).get_columns("background_jobs")}
    added: list[str] = []
    with engine.begin() as conn:
        for name, (postgres_type, sqlite_type) in JOB_COLUMNS.items():
            if name in present:
                continue
            column_type = postgres_type if dialect == "postgresql" else sqlite_type
            conn.execute(text(f"ALTER TABLE background_jobs ADD COLUMN {name} {column_type};"))
            added.append(name)
    return added


def reconcile_active_jobs(engine: Engine) -> dict[str, int]:
    """Leave at most one queued or running job per task name.

    Keeps the running job whose lease was renewed most recently - it is the one
    that may still have a worker behind it - and otherwise the newest queued
    job. Everything else for that task is failed, with the survivor named so
    the history stays readable.
    """
    dialect = engine.dialect.name
    failed_by_task: dict[str, int] = {}
    with engine.begin() as conn:
        tasks = [
            row[0]
            for row in conn.execute(
                text(
                    "SELECT task_name FROM background_jobs WHERE status IN ('queued', 'running') "
                    "GROUP BY task_name HAVING COUNT(*) > 1"
                )
            )
        ]
        for task_name in tasks:
            rows = conn.execute(
                text(
                    "SELECT job_id, status, updated_at, created_at FROM background_jobs "
                    "WHERE task_name = :task AND status IN ('queued', 'running') "
                    "ORDER BY CASE WHEN status = 'running' THEN 0 ELSE 1 END, "
                    "updated_at DESC, created_at DESC, job_id DESC"
                ),
                {"task": task_name},
            ).all()
            survivor = rows[0][0]
            losers = [row[0] for row in rows[1:]]
            conn.execute(
                text(
                    "UPDATE background_jobs SET status = 'failed', "
                    f"finished_at = {_now(dialect)}, updated_at = {_now(dialect)}, "
                    "error_message = :reason "
                    "WHERE task_name = :task AND status IN ('queued', 'running') "
                    "AND job_id <> :survivor"
                ),
                {
                    "task": task_name,
                    "survivor": survivor,
                    "reason": (
                        "failed by add_background_jobs: more than one job was active for "
                        f"{task_name}, and {survivor} was kept as the newest live one"
                    ),
                },
            )
            failed_by_task[task_name] = len(losers)
    return failed_by_task


def verify(engine: Engine) -> dict[str, object]:
    """Read the live schema back and prove the migration achieved its goal."""
    inspector = inspect(engine)
    columns = [column["name"] for column in inspector.get_columns("background_jobs")]
    indexes = sorted(index["name"] for index in inspector.get_indexes("background_jobs"))
    with engine.connect() as conn:
        duplicates = conn.execute(
            text(
                "SELECT task_name, COUNT(*) FROM background_jobs "
                "WHERE status IN ('queued', 'running') GROUP BY task_name HAVING COUNT(*) > 1"
            )
        ).all()
    missing = [name for name in (*JOB_COLUMNS, "id", "job_id") if name not in columns]
    report = {
        "columns": columns,
        "indexes": indexes,
        "missing_columns": missing,
        "duplicate_active_tasks": [row[0] for row in duplicates],
        "active_index_present": ACTIVE_JOB_INDEX in indexes,
    }
    if missing or report["duplicate_active_tasks"] or not report["active_index_present"]:
        raise RuntimeError(f"background_jobs is not in the expected shape: {report}")
    return report


def migrate(engine: Engine | None = None) -> dict[str, object]:
    engine = engine or get_engine()

    BackgroundJob.__table__.create(bind=engine, checkfirst=True)
    print("  ensured background_jobs")

    added = _add_missing_job_columns(engine)
    print(f"  added missing columns: {added or 'none'}")

    failed = reconcile_active_jobs(engine)
    print(f"  reconciled duplicate active jobs: {failed or 'none'}")

    with engine.begin() as conn:
        conn.execute(
            text(
                f"CREATE UNIQUE INDEX IF NOT EXISTS {ACTIVE_JOB_INDEX} ON background_jobs "
                "(task_name) WHERE status IN ('queued', 'running');"
            )
        )
        print(f"  ensured {ACTIVE_JOB_INDEX}")
        for index, column in JOB_INDEXES:
            unique = "UNIQUE " if column == "job_id" else ""
            conn.execute(
                text(f"CREATE {unique}INDEX IF NOT EXISTS {index} ON background_jobs ({column});")
            )
            print(f"  ensured {index}")

    if inspect(engine).has_table("predictions"):
        with engine.begin() as conn:
            present = {c["name"] for c in inspect(engine).get_columns("predictions")}
            for name, sql_type in PREDICTION_COLUMNS:
                if name in present:
                    continue
                conn.execute(text(f"ALTER TABLE predictions ADD COLUMN {name} {sql_type};"))
                print(f"  ensured predictions.{name} {sql_type}")
            for index, column in PREDICTION_INDEXES:
                conn.execute(text(f"CREATE INDEX IF NOT EXISTS {index} ON predictions ({column});"))
                print(f"  ensured {index}")

    report = verify(engine)
    print("")
    print("  background_jobs columns:", report["columns"])
    print("  background_jobs indexes:", report["indexes"])
    return report


if __name__ == "__main__":
    migrate()
