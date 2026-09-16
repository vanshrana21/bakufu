"""
Bring an existing database up to src/db/models.py for background jobs and
prediction lookups.

  background_jobs                created, or upgraded column by column
  background_jobs.claim_fence    the fence model promotion is judged against
  background_jobs_fence_seq      issues those fences on PostgreSQL
  uq_background_jobs_claim_fence no two claims may hold the same fence
  artifact_version etc.          what each job published, the recovery ledger
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

from src.db.models import BackgroundJob, JobOutbox
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
    "artifact_version": ("VARCHAR(128)", "VARCHAR(128)"),
    "artifact_sha256": ("VARCHAR(64)", "VARCHAR(64)"),
    "artifact_published_at": ("TIMESTAMPTZ", "DATETIME"),
    "artifact_activated_at": ("TIMESTAMPTZ", "DATETIME"),
}

#: A column added to a live table arrives nullable whatever the model says, so
#: the ones the model declares NOT NULL are backfilled and tightened. Only
#: PostgreSQL can do that in place; SQLite would need the table rebuilt, and it
#: is the tests' database, so verify() reports nullability there without failing.
JOB_NOT_NULL = ("job_id", "task_name", "status", "claim_fence", "created_at", "updated_at")

JOB_BACKFILL = {"claim_fence": "0"}

JOB_INDEXES = (
    ("ix_background_jobs_job_id", "job_id"),
    ("ix_background_jobs_status", "status"),
)

#: Hands out claim fences on PostgreSQL (src/db/models.py FENCE_SEQUENCE).
FENCE_SEQUENCE = "background_jobs_fence_seq"
FENCE_INDEX = "uq_background_jobs_claim_fence"

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


def _tighten_not_null(engine: Engine) -> list[str]:
    """Backfill and enforce NOT NULL where the model declares it."""
    if engine.dialect.name != "postgresql":
        return []
    live = {column["name"]: column for column in inspect(engine).get_columns("background_jobs")}
    tightened: list[str] = []
    with engine.begin() as conn:
        for name in JOB_NOT_NULL:
            column = live.get(name)
            if column is None or not column["nullable"]:
                continue
            default = JOB_BACKFILL.get(name)
            if default is not None:
                conn.execute(text(f"UPDATE background_jobs SET {name} = {default} WHERE {name} IS NULL;"))
            conn.execute(text(f"ALTER TABLE background_jobs ALTER COLUMN {name} SET NOT NULL;"))
            tightened.append(name)
    return tightened


def _ensure_fence_sequence(engine: Engine) -> None:
    """Create the fence sequence and move it past every fence already issued."""
    if engine.dialect.name != "postgresql":
        return
    with engine.begin() as conn:
        conn.execute(text(f"CREATE SEQUENCE IF NOT EXISTS {FENCE_SEQUENCE};"))
        conn.execute(
            text(
                f"SELECT setval('{FENCE_SEQUENCE}', "
                "GREATEST((SELECT COALESCE(MAX(claim_fence), 0) FROM background_jobs), 1));"
            )
        )


def reconcile_duplicate_fences(engine: Engine) -> int:
    """Clear fences shared by more than one row, so the unique index can be built.

    Only a database written by the previous MAX(claim_fence) + 1 allocator can
    hold duplicates. The rows are finished jobs by then, so their fences are
    history; zeroing them keeps the row and its artifact record intact.
    """
    with engine.begin() as conn:
        duplicates = [
            row[0]
            for row in conn.execute(
                text(
                    "SELECT claim_fence FROM background_jobs WHERE claim_fence > 0 "
                    "GROUP BY claim_fence HAVING COUNT(*) > 1"
                )
            )
        ]
        cleared = 0
        for fence in duplicates:
            rows = conn.execute(
                text(
                    "SELECT job_id FROM background_jobs WHERE claim_fence = :fence "
                    "ORDER BY updated_at DESC, job_id DESC"
                ),
                {"fence": fence},
            ).all()
            for (job_id,) in rows[1:]:
                conn.execute(
                    text("UPDATE background_jobs SET claim_fence = 0 WHERE job_id = :job_id"),
                    {"job_id": job_id},
                )
                cleared += 1
    return cleared


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
    """Read the live schema back and check it against src/db/models.py.

    Columns, nullability, index names and index uniqueness all come from the
    model rather than a list maintained here, so a column added to the model
    without a migration step shows up as a failure instead of passing quietly.
    Nullability is only enforced on PostgreSQL - SQLite cannot alter a column in
    place - so it is reported, not fatal, elsewhere.
    """
    inspector = inspect(engine)
    live_columns = {column["name"]: column for column in inspector.get_columns("background_jobs")}
    live_indexes = {index["name"]: index for index in inspector.get_indexes("background_jobs")}
    model = BackgroundJob.__table__

    missing = sorted({column.name for column in model.columns} - set(live_columns))
    nullability = sorted(
        column.name
        for column in model.columns
        if column.name in live_columns
        and bool(live_columns[column.name]["nullable"]) != bool(column.nullable)
    )
    expected_indexes = {index.name: index for index in model.indexes}
    expected_indexes.update({name: None for name, _column in JOB_INDEXES})
    missing_indexes = sorted(set(expected_indexes) - set(live_indexes))
    not_unique = sorted(
        name
        for name, index in expected_indexes.items()
        if index is not None and index.unique and name in live_indexes
        and not live_indexes[name]["unique"]
    )

    with engine.connect() as conn:
        duplicate_tasks = [
            row[0]
            for row in conn.execute(
                text(
                    "SELECT task_name, COUNT(*) FROM background_jobs "
                    "WHERE status IN ('queued', 'running') GROUP BY task_name HAVING COUNT(*) > 1"
                )
            )
        ]
        duplicate_fences = [
            row[0]
            for row in conn.execute(
                text(
                    "SELECT claim_fence FROM background_jobs WHERE claim_fence > 0 "
                    "GROUP BY claim_fence HAVING COUNT(*) > 1"
                )
            )
        ]

    report = {
        "columns": sorted(live_columns),
        "indexes": sorted(live_indexes),
        "missing_columns": missing,
        "nullability_mismatch": nullability,
        "missing_indexes": missing_indexes,
        "indexes_not_unique": not_unique,
        "duplicate_active_tasks": duplicate_tasks,
        "duplicate_fences": duplicate_fences,
        "active_index_present": ACTIVE_JOB_INDEX in live_indexes,
        "fence_index_present": FENCE_INDEX in live_indexes,
    }
    fatal = (
        missing
        or missing_indexes
        or not_unique
        or duplicate_tasks
        or duplicate_fences
        or (nullability if engine.dialect.name == "postgresql" else [])
    )
    if fatal:
        raise RuntimeError(f"background_jobs is not in the expected shape: {report}")
    return report


def migrate(engine: Engine | None = None) -> dict[str, object]:
    engine = engine or get_engine()

    BackgroundJob.__table__.create(bind=engine, checkfirst=True)
    print("  ensured background_jobs")
    JobOutbox.__table__.create(bind=engine, checkfirst=True)
    print("  ensured job_outbox")

    added = _add_missing_job_columns(engine)
    print(f"  added missing columns: {added or 'none'}")

    tightened = _tighten_not_null(engine)
    print(f"  tightened to NOT NULL: {tightened or 'none'}")

    _ensure_fence_sequence(engine)
    print(f"  ensured {FENCE_SEQUENCE}" if engine.dialect.name == "postgresql" else "  fence sequence: n/a")

    failed = reconcile_active_jobs(engine)
    print(f"  reconciled duplicate active jobs: {failed or 'none'}")

    cleared = reconcile_duplicate_fences(engine)
    print(f"  cleared duplicate claim fences: {cleared}")

    with engine.begin() as conn:
        conn.execute(
            text(
                f"CREATE UNIQUE INDEX IF NOT EXISTS {ACTIVE_JOB_INDEX} ON background_jobs "
                "(task_name) WHERE status IN ('queued', 'running');"
            )
        )
        print(f"  ensured {ACTIVE_JOB_INDEX}")
        conn.execute(
            text(
                f"CREATE UNIQUE INDEX IF NOT EXISTS {FENCE_INDEX} ON background_jobs "
                "(claim_fence) WHERE claim_fence > 0;"
            )
        )
        print(f"  ensured {FENCE_INDEX}")
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
