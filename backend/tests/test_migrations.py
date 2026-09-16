"""scripts/migrations/add_background_jobs.py against databases in real states.

The migration has to be safe to run on a database that already has jobs in it.
Creating the one-active-job index on a table that holds two active rows fails,
so duplicates are reconciled first by an explicit rule; and a background_jobs
table from an older release is upgraded column by column rather than skipped.
"""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import pytest
from sqlalchemy import Engine, create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

from scripts.migrations.add_background_jobs import (
    ACTIVE_JOB_INDEX,
    FENCE_INDEX,
    migrate,
    reconcile_active_jobs,
)
from src.db.models import BackgroundJob
from src.worker import jobs

TASK = jobs.TRAIN_TASK_NAME


@pytest.fixture()
def engine(tmp_path: Path) -> Engine:
    created = create_engine(f"sqlite:///{tmp_path / 'legacy.db'}")
    yield created
    created.dispose()


def _legacy_table(engine: Engine) -> None:
    """background_jobs as an earlier release left it: no one-active-job index."""
    BackgroundJob.__table__.create(engine)
    with engine.begin() as conn:
        conn.execute(text(f"DROP INDEX IF EXISTS {ACTIVE_JOB_INDEX}"))


def _insert(engine: Engine, job_id: str, status: str, minutes_ago: float = 0.0, task: str = TASK) -> None:
    stamp = jobs.utcnow() - timedelta(minutes=minutes_ago)
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO background_jobs (job_id, task_name, status, created_at, updated_at) "
                "VALUES (:job_id, :task, :status, :stamp, :stamp)"
            ),
            {"job_id": job_id, "task": task, "status": status, "stamp": stamp},
        )


def _statuses(engine: Engine) -> dict[str, str]:
    with engine.connect() as conn:
        return dict(conn.execute(text("SELECT job_id, status FROM background_jobs")).all())


# --- mandatory 9: zero, one, and many recent duplicates ------------------


def test_migrating_an_empty_database(engine: Engine) -> None:
    report = migrate(engine)
    assert report["active_index_present"] and report["missing_columns"] == []
    assert "claim_fence" in report["columns"]


def test_migrating_with_one_active_job_keeps_it(engine: Engine) -> None:
    _legacy_table(engine)
    _insert(engine, "only-one", "running")

    migrate(engine)

    assert _statuses(engine) == {"only-one": "running"}


def test_migrating_with_many_recent_duplicates(engine: Engine) -> None:
    """The case that used to fail: duplicates too new for the one-hour cutoff."""
    _legacy_table(engine)
    _insert(engine, "queued-old", "queued", minutes_ago=3)
    _insert(engine, "running-stale", "running", minutes_ago=2)
    _insert(engine, "running-fresh", "running", minutes_ago=0.1)
    _insert(engine, "queued-new", "queued", minutes_ago=0.05)
    _insert(engine, "other-task", "queued", task="something_else")

    report = migrate(engine)

    statuses = _statuses(engine)
    # The running job with the most recent heartbeat survives; the rest fail.
    assert statuses["running-fresh"] == "running"
    assert statuses["running-stale"] == "failed"
    assert statuses["queued-old"] == "failed"
    assert statuses["queued-new"] == "failed"
    # A different task keeps its own active job.
    assert statuses["other-task"] == "queued"
    assert report["duplicate_active_tasks"] == []

    with engine.connect() as conn:
        reason = conn.execute(
            text("SELECT error_message FROM background_jobs WHERE job_id = 'queued-old'")
        ).scalar()
    assert "running-fresh" in reason


def test_queued_duplicates_keep_the_newest_when_none_is_running(engine: Engine) -> None:
    _legacy_table(engine)
    _insert(engine, "older", "queued", minutes_ago=5)
    _insert(engine, "newest", "queued", minutes_ago=0.1)

    reconcile_active_jobs(engine)

    assert _statuses(engine) == {"older": "failed", "newest": "queued"}


def test_the_index_bites_after_the_migration(engine: Engine) -> None:
    migrate(engine)
    _insert(engine, "first", "queued")
    with pytest.raises(IntegrityError):
        _insert(engine, "second", "running")


# --- mandatory 10: a partially existing table ----------------------------


def test_migrating_a_table_from_an_older_release(engine: Engine) -> None:
    """A background_jobs with only the columns that release knew about."""
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE background_jobs ("
                " id INTEGER PRIMARY KEY,"
                " job_id VARCHAR(64),"
                " task_name VARCHAR(64),"
                " status VARCHAR(16) DEFAULT 'queued',"
                " created_at DATETIME)"
            )
        )
        conn.execute(
            text(
                "INSERT INTO background_jobs (job_id, task_name, status, created_at) "
                "VALUES ('legacy', :task, 'running', :stamp)"
            ),
            {"task": TASK, "stamp": jobs.utcnow()},
        )

    report = migrate(engine)

    columns = {column["name"] for column in inspect(engine).get_columns("background_jobs")}
    assert {"claim_fence", "progress", "result_data", "error_message", "started_at",
            "finished_at", "updated_at"} <= columns
    assert report["missing_columns"] == []
    assert ACTIVE_JOB_INDEX in report["indexes"]
    assert _statuses(engine) == {"legacy": "running"}


def test_duplicate_fences_from_the_old_allocator_are_cleared(engine: Engine) -> None:
    """A database written by MAX(claim_fence) + 1 can hold collisions."""
    _legacy_table(engine)
    with engine.begin() as conn:
        conn.execute(text(f"DROP INDEX IF EXISTS {FENCE_INDEX}"))
        for job_id, task in (("a", "task-a"), ("b", "task-b")):
            conn.execute(
                text(
                    "INSERT INTO background_jobs (job_id, task_name, status, claim_fence, created_at, updated_at) "
                    "VALUES (:job_id, :task, 'completed', 5, :stamp, :stamp)"
                ),
                {"job_id": job_id, "task": task, "stamp": jobs.utcnow()},
            )

    report = migrate(engine)

    assert report["duplicate_fences"] == []
    assert report["fence_index_present"]
    with engine.connect() as conn:
        fences = dict(conn.execute(text("SELECT job_id, claim_fence FROM background_jobs")).all())
    # One row keeps the fence; the other is zeroed, and both rows survive.
    assert sorted(fences.values()) == [0, 5]


def test_the_artifact_ledger_columns_are_added(engine: Engine) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE background_jobs ("
                " id INTEGER PRIMARY KEY, job_id VARCHAR(64), task_name VARCHAR(64),"
                " status VARCHAR(16) DEFAULT 'queued', created_at DATETIME)"
            )
        )

    report = migrate(engine)

    assert {"artifact_version", "artifact_sha256", "artifact_published_at", "artifact_activated_at"} <= set(
        report["columns"]
    )


def test_verification_catches_a_missing_index(engine: Engine) -> None:
    """verify() checks the model's indexes, not a list kept in the migration."""
    from scripts.migrations.add_background_jobs import verify

    migrate(engine)
    with engine.begin() as conn:
        conn.execute(text(f"DROP INDEX {FENCE_INDEX}"))

    with pytest.raises(RuntimeError, match="not in the expected shape"):
        verify(engine)


def test_verification_checks_every_column_the_model_declares(engine: Engine) -> None:
    from scripts.migrations import add_background_jobs

    _legacy_table(engine)
    # A column the migration does not know about, but the model does.
    monkey = dict(add_background_jobs.JOB_COLUMNS)
    monkey.pop("artifact_sha256")
    original, add_background_jobs.JOB_COLUMNS = add_background_jobs.JOB_COLUMNS, monkey
    try:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE background_jobs DROP COLUMN artifact_sha256"))
        with pytest.raises(RuntimeError, match="artifact_sha256"):
            migrate(engine)
    finally:
        add_background_jobs.JOB_COLUMNS = original


def test_the_migration_is_idempotent(engine: Engine) -> None:
    first = migrate(engine)
    second = migrate(engine)
    assert first["columns"] == second["columns"]
    assert first["indexes"] == second["indexes"]


def test_verification_fails_loudly_on_a_table_it_could_not_fix(engine: Engine, monkeypatch) -> None:
    """The migration must not report success on a schema it did not reach."""
    from scripts.migrations import add_background_jobs

    _legacy_table(engine)
    _insert(engine, "one", "queued")
    _insert(engine, "two", "running")
    monkeypatch.setattr(add_background_jobs, "reconcile_active_jobs", lambda _engine: {})

    with pytest.raises(Exception):  # noqa: B017 - either the index or verify() rejects it
        migrate(engine)
