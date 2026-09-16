"""State transitions for rows in background_jobs.

A job moves queued -> running -> completed | failed. Each transition is one
conditional UPDATE, so the API, a worker and a redelivered copy of the same task
can race without corrupting a job or training twice.

A running job holds a lease: its worker touches `updated_at` every
TRAINING_HEARTBEAT_SECONDS, and a job whose lease is older than
TRAINING_LEASE_SECONDS has lost its worker. `started_at` is the fencing token:
each claim stamps a new one, and a worker's writes land only while the row
still carries its stamp.

All timestamps come from Python in UTC, so SQLite (the tests) and Postgres
compare the same values.
"""

from __future__ import annotations

import zlib
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import and_, func, or_, select, text, update
from sqlalchemy.orm import Session

from src.config.settings import settings
from src.db import session as db_session
from src.db.models import FENCE_SEQUENCE, BackgroundJob

#: BackgroundJob.task_name for POST /train.
TRAIN_TASK_NAME = "train_pu_xgboost"

#: The statuses that occupy a task's single active slot.
ACTIVE_STATUSES: tuple[str, ...] = ("queued", "running")


def utcnow() -> datetime:
    return datetime.now(UTC)


# --- API side: run inside the request's transaction ----------------------


def lock_task_starts(db: Session, task_name: str) -> None:
    """Serialise job creation for `task_name` until this transaction ends.

    A transaction-scoped advisory lock, so it also holds on Supabase's
    transaction pooler, and the commit or rollback ending the request releases
    it. On other databases the partial unique index on background_jobs is the
    guard.
    """
    if db.get_bind().dialect.name != "postgresql":
        return
    key = zlib.crc32(f"background_jobs:{task_name}".encode())
    db.execute(text("SELECT pg_advisory_xact_lock(CAST(:key AS BIGINT))"), {"key": key})


def lock_model_promotion(db: Session, task_name: str) -> None:
    """Serialise model promotion across hosts for the length of a transaction."""
    lock_task_starts(db, f"model_promotion:{task_name}")


def expire_stale_jobs(db: Session, task_name: str, now: datetime) -> int:
    """Fail active jobs that no worker will ever finish, freeing the slot.

    Queued past TRAINING_QUEUE_TIMEOUT_SECONDS: no worker ever claimed it.
    Running without a heartbeat for TRAINING_LEASE_SECONDS: its worker crashed,
    was killed, or hit the hard time limit.
    """
    unclaimed = db.execute(
        update(BackgroundJob)
        .where(
            BackgroundJob.task_name == task_name,
            BackgroundJob.status == "queued",
            BackgroundJob.created_at < now - timedelta(seconds=settings.TRAINING_QUEUE_TIMEOUT_SECONDS),
        )
        .values(
            status="failed",
            finished_at=now,
            updated_at=now,
            error_message=(
                f"no worker claimed this job within {settings.TRAINING_QUEUE_TIMEOUT_SECONDS} s; "
                "check that Redis and the Celery worker are running"
            ),
        )
        .execution_options(synchronize_session=False)
    )
    abandoned = db.execute(
        update(BackgroundJob)
        .where(
            BackgroundJob.task_name == task_name,
            BackgroundJob.status == "running",
            BackgroundJob.updated_at < now - timedelta(seconds=settings.TRAINING_LEASE_SECONDS),
        )
        .values(
            status="failed",
            finished_at=now,
            updated_at=now,
            error_message=(
                f"the worker stopped renewing its lease for over {settings.TRAINING_LEASE_SECONDS} s: "
                "it crashed, was killed, or hit the hard time limit"
            ),
        )
        .execution_options(synchronize_session=False)
    )
    return unclaimed.rowcount + abandoned.rowcount


def count_active_jobs(db: Session, task_name: str) -> int:
    """SELECT COUNT(*) FROM background_jobs WHERE status IN ('queued', 'running') for one task."""
    count = db.scalar(
        select(func.count())
        .select_from(BackgroundJob)
        .where(BackgroundJob.task_name == task_name, BackgroundJob.status.in_(ACTIVE_STATUSES))
    )
    return int(count or 0)


def active_job(db: Session, task_name: str) -> BackgroundJob | None:
    """The newest queued or running job for `task_name`."""
    return db.scalars(
        select(BackgroundJob)
        .where(BackgroundJob.task_name == task_name, BackgroundJob.status.in_(ACTIVE_STATUSES))
        .order_by(BackgroundJob.created_at.desc())
        .limit(1)
    ).first()


def fail_queued_job(db: Session, job_id: str, reason: str, now: datetime) -> bool:
    """Fail a job that has not started, e.g. one whose message never reached the broker."""
    result = db.execute(
        update(BackgroundJob)
        .where(BackgroundJob.job_id == job_id, BackgroundJob.status == "queued")
        .values(status="failed", finished_at=now, updated_at=now, error_message=reason)
        .execution_options(synchronize_session=False)
    )
    return result.rowcount == 1


# --- worker side: each call is its own short transaction -----------------


@dataclass(frozen=True)
class Claim:
    """What a worker found when it tried to claim a job."""

    #: The fencing token - the job's new started_at - when claimed, else None.
    token: datetime | None
    #: The job's status as found; None when the row does not exist.
    status: str | None
    #: The fence this claim took: strictly greater than every fence before it,
    #: and what model promotion is judged against. 0 when nothing was claimed.
    fence: int = 0


def _next_fence(db: Session) -> Any:
    """An expression yielding a fence no earlier claim has held.

    PostgreSQL takes it from a sequence, which hands out each number once even
    under concurrent claims. SQLite has no sequences, but it serialises writers,
    so reading the maximum inside the claim's own write transaction is safe
    there; the partial unique index on claim_fence rejects a collision either
    way rather than letting two claims share a fence.
    """
    if db.get_bind().dialect.name == "postgresql":
        return FENCE_SEQUENCE.next_value()
    return (
        select(func.coalesce(func.max(BackgroundJob.claim_fence), 0) + 1)
        .select_from(BackgroundJob)
        .scalar_subquery()
    )


def claim_job(job_id: str, now: datetime) -> Claim:
    """Take a queued job, or a running one whose lease has lapsed."""
    lease_cutoff = now - timedelta(seconds=settings.TRAINING_LEASE_SECONDS)
    with db_session.SessionLocal() as db, db.begin():
        claimed = db.execute(
            update(BackgroundJob)
            .where(
                BackgroundJob.job_id == job_id,
                or_(
                    BackgroundJob.status == "queued",
                    and_(BackgroundJob.status == "running", BackgroundJob.updated_at < lease_cutoff),
                ),
            )
            .values(
                status="running",
                progress=0.0,
                started_at=now,
                updated_at=now,
                finished_at=None,
                error_message=None,
                # The database, not a clock, decides which claim is newer.
                claim_fence=_next_fence(db),
            )
            .execution_options(synchronize_session=False)
        ).rowcount
        if claimed == 1:
            fence = db.scalar(select(BackgroundJob.claim_fence).where(BackgroundJob.job_id == job_id))
            return Claim(token=now, status="running", fence=int(fence or 0))
        status = db.scalar(select(BackgroundJob.status).where(BackgroundJob.job_id == job_id))
        return Claim(token=None, status=status)


def owns_job(job_id: str, token: datetime) -> bool:
    """Whether the claim identified by `token` still owns this running job.

    Read-only, for the check model promotion makes inside the registry lock.
    """
    with db_session.SessionLocal() as db:
        return (
            db.scalar(
                select(func.count())
                .select_from(BackgroundJob)
                .where(
                    BackgroundJob.job_id == job_id,
                    BackgroundJob.status == "running",
                    BackgroundJob.started_at == token,
                )
            )
            or 0
        ) == 1


def renew_lease(job_id: str, token: datetime, now: datetime) -> bool:
    """Heartbeat. False once the job has ended or another worker has claimed it."""
    with db_session.SessionLocal() as db, db.begin():
        result = db.execute(
            update(BackgroundJob)
            .where(
                BackgroundJob.job_id == job_id,
                BackgroundJob.status == "running",
                BackgroundJob.started_at == token,
            )
            .values(updated_at=now)
            .execution_options(synchronize_session=False)
        )
        return result.rowcount == 1


@dataclass(frozen=True)
class PublishedArtifact:
    """What the database says a job published."""

    version: str
    sha256: str | None
    published_at: datetime | None
    activated_at: datetime | None


def record_publication(
    job_id: str,
    token: datetime,
    version: str,
    sha256: str,
    now: datetime,
    activated: bool,
) -> bool:
    """Write what this job published, fenced by the claim that published it.

    Called the moment the artifact is in the registry, so the database - not a
    scan of the versions directory - is what says the job has published.
    """
    with db_session.SessionLocal() as db, db.begin():
        result = db.execute(
            update(BackgroundJob)
            .where(BackgroundJob.job_id == job_id, BackgroundJob.started_at == token)
            .values(
                artifact_version=version,
                artifact_sha256=sha256,
                artifact_published_at=now,
                artifact_activated_at=now if activated else None,
                updated_at=now,
            )
            .execution_options(synchronize_session=False)
        )
        return result.rowcount == 1


def published_artifact(job_id: str) -> PublishedArtifact | None:
    """What this job published, if anything. The recovery path's source of truth."""
    with db_session.SessionLocal() as db:
        row = db.execute(
            select(
                BackgroundJob.artifact_version,
                BackgroundJob.artifact_sha256,
                BackgroundJob.artifact_published_at,
                BackgroundJob.artifact_activated_at,
            ).where(BackgroundJob.job_id == job_id)
        ).first()
    if row is None or not row[0]:
        return None
    return PublishedArtifact(version=row[0], sha256=row[1], published_at=row[2], activated_at=row[3])


def published_artifacts(task_name: str, limit: int = 20) -> list[PublishedArtifact]:
    """The most recent publications on record, newest first."""
    with db_session.SessionLocal() as db:
        rows = db.execute(
            select(
                BackgroundJob.artifact_version,
                BackgroundJob.artifact_sha256,
                BackgroundJob.artifact_published_at,
                BackgroundJob.artifact_activated_at,
            )
            .where(BackgroundJob.task_name == task_name, BackgroundJob.artifact_version.is_not(None))
            .order_by(BackgroundJob.artifact_published_at.desc())
            .limit(limit)
        ).all()
    return [
        PublishedArtifact(version=row[0], sha256=row[1], published_at=row[2], activated_at=row[3])
        for row in rows
    ]


def record_outcome(job_id: str, token: datetime, **fields: Any) -> bool:
    """Write a final state unless another worker has claimed the job since.

    Not conditional on status: if the API expired this job while its worker was
    cut off from the database, the outcome the worker actually reached wins.
    """
    with db_session.SessionLocal() as db, db.begin():
        result = db.execute(
            update(BackgroundJob)
            .where(BackgroundJob.job_id == job_id, BackgroundJob.started_at == token)
            .values(**fields)
            .execution_options(synchronize_session=False)
        )
        return result.rowcount == 1
