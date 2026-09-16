"""Celery tasks. Run them with:

    celery -A src.worker.celery_app worker --queues training --concurrency 1 --loglevel INFO
"""

from __future__ import annotations

import logging
import shutil
import threading
import time
import traceback
from datetime import datetime
from typing import Any

from celery import Task
from sqlalchemy.exc import SQLAlchemyError

from src.config.settings import settings
from src.db import session as db_session
from src.worker import jobs
from src.worker.celery_app import TRAIN_TASK, celery_app

logger = logging.getLogger("worker.training")


class RegistryMismatch(RuntimeError):
    """The database says a job published something the registry cannot produce."""

#: Seen a live lease? Look again once it would have lapsed.
LEASE_RECHECK_SECONDS = settings.TRAINING_LEASE_SECONDS + settings.TRAINING_HEARTBEAT_SECONDS
#: Enough re-checks to outlast a run that goes all the way to the hard time limit.
MAX_RETRIES = settings.TRAINING_TIME_LIMIT_SECONDS // LEASE_RECHECK_SECONDS + 5
#: Attempts at writing the outcome before the database is given up on.
OUTCOME_WRITE_ATTEMPTS = 5


@celery_app.task(
    bind=True,
    name=TRAIN_TASK,
    max_retries=MAX_RETRIES,
    soft_time_limit=settings.TRAINING_SOFT_TIME_LIMIT_SECONDS,
    time_limit=settings.TRAINING_TIME_LIMIT_SECONDS,
)
def train_prospectivity_model(self: Task, job_id: str) -> str:
    """Claim job `job_id`, retrain the prospectivity model, record the outcome.

    Safe to deliver more than once: only the delivery that claims the job
    trains, and any other copy returns without touching the model.
    """
    try:
        claim = jobs.claim_job(job_id, jobs.utcnow())
    except SQLAlchemyError as exc:
        logger.warning("could not claim training job %s; retrying", job_id, exc_info=True)
        raise self.retry(exc=exc, countdown=settings.TRAINING_HEARTBEAT_SECONDS) from exc

    if claim.token is None:
        if claim.status == "running":
            # A live lease: another delivery is training, or its worker has just
            # died and the lease has yet to lapse. Look again once it would have.
            raise self.retry(countdown=LEASE_RECHECK_SECONDS)
        logger.info("training job %s is %s; nothing to do", job_id, claim.status or "missing")
        return claim.status or "missing"

    run_training_job(job_id, claim.token, claim.fence)
    return "claimed"


def run_training_job(job_id: str, token: datetime, fence: int) -> None:
    """Train while renewing the job's lease, then record how it went."""
    with _LeaseHeartbeat(job_id, token):
        try:
            published = _train_and_publish(job_id, token, fence)
        except Exception as exc:  # noqa: BLE001 - surfaced through GET /train/{task_id}
            outcome: dict[str, Any] = {
                "status": "failed",
                "error_message": f"{type(exc).__name__}: {exc}\n{traceback.format_exc()}",
            }
        else:
            outcome = {
                "status": "completed",
                "progress": 100.0,
                "result_data": {
                    "detail": (
                        f"model retrained and published as {published.version}"
                        + ("; serving now uses it" if published.activated else "; not yet activated")
                    ),
                    "version": published.version,
                    "model_path": str(published.path),
                    "activated": published.activated,
                },
            }
    _record_outcome(job_id, token, outcome)


def _train_and_publish(job_id: str, token: datetime, fence: int):
    """Train into this claim's own directory and publish it to the registry.

    Nothing is written where inference looks. The artifact is validated, moved
    into an immutable version directory, and - only when the server is
    configured to activate on success - the pointer is moved to it. Both the
    fence comparison and the ownership check happen inside the registry lock
    that also writes the pointer, so a worker that stalled and lost its job
    cannot publish over a newer artifact.
    """
    # Imported here, inside the forked worker process: torch and XGBoost must
    # not start their thread pools in the parent that does the forking.
    from src.models import registry
    from src.models.prospectivity.train_pu_xgboost import main as train_main

    recovered = _recover_published(job_id, fence)
    if recovered is not None:
        return recovered

    staged = registry.staging_dir(job_id, fence)
    shutil.rmtree(staged, ignore_errors=True)
    staged.mkdir(parents=True, exist_ok=True)
    try:
        # An explicit argv: the parser would otherwise read the worker's own
        # command line and exit.
        train_main(
            [],
            save_path=staged / registry.MODEL_FILENAME,
            metrics_path=staged / registry.METRICS_FILENAME,
        )
        # The advisory lock serialises promotion across hosts; the registry lock
        # inside publish() covers this host and the pointer write itself.
        with db_session.SessionLocal() as db, db.begin():
            jobs.lock_model_promotion(db, jobs.TRAIN_TASK_NAME)
            published = registry.publish(
                staged=staged,
                job_id=job_id,
                fence=fence,
                activate=settings.TRAINING_ACTIVATE_ON_SUCCESS,
                still_owns_job=lambda: jobs.owns_job(job_id, token),
            )
    finally:
        shutil.rmtree(staged, ignore_errors=True)

    # Recorded before the outcome, and fenced by the same claim: a worker that
    # dies here leaves a row that names the artifact, which is what the next
    # delivery reads instead of guessing from the versions directory.
    if not jobs.record_publication(
        job_id,
        token,
        published.version,
        registry.sha256(published.path),
        jobs.utcnow(),
        activated=published.activated,
    ):
        logger.warning(
            "job %s published %s but no longer owns its row; the outcome will be discarded",
            job_id, published.version,
        )
    return published


def _recover_published(job_id: str, fence: int):
    """Return what this job already published, or None if it published nothing.

    The database is the ledger. The artifact it names still has to be there and
    still has to match its digest - a registry restored from a stale backup, or
    a version deleted by hand, must not be reported as a healthy outcome.
    """
    from src.models import registry

    recorded = jobs.published_artifact(job_id)
    if recorded is None:
        return None

    model_file = registry.version_dir(recorded.version) / registry.MODEL_FILENAME
    if not model_file.exists():
        raise RegistryMismatch(
            f"job {job_id} published {recorded.version}, but that version is missing from "
            f"{registry.VERSIONS_DIR}; the registry and the database disagree"
        )
    if recorded.sha256 and registry.sha256(model_file) != recorded.sha256:
        raise RegistryMismatch(
            f"job {job_id} published {recorded.version}, but the artifact on disk no longer "
            "matches the digest recorded for it"
        )

    pointer = registry.read_pointer() or {}
    logger.info("training job %s already published %s; recording that", job_id, recorded.version)
    return registry.PublishedVersion(
        version=recorded.version,
        path=model_file,
        fence=fence,
        job_id=job_id,
        activated=pointer.get("version") == recorded.version,
    )


def _record_outcome(job_id: str, token: datetime, outcome: dict[str, Any]) -> None:
    for attempt in range(1, OUTCOME_WRITE_ATTEMPTS + 1):
        now = jobs.utcnow()
        try:
            recorded = jobs.record_outcome(job_id, token, finished_at=now, updated_at=now, **outcome)
        except SQLAlchemyError:
            logger.warning(
                "could not record the outcome of training job %s (attempt %d of %d)",
                job_id, attempt, OUTCOME_WRITE_ATTEMPTS, exc_info=True,
            )
            if attempt < OUTCOME_WRITE_ATTEMPTS:
                time.sleep(min(2**attempt, 30))
            continue
        if not recorded:
            logger.warning(
                "training job %s was claimed by another worker; discarding this %s outcome",
                job_id, outcome["status"],
            )
        return
    logger.error(
        "gave up recording the outcome of training job %s; its lease will lapse and it will read as failed",
        job_id,
    )


class _LeaseHeartbeat:
    """Renews a running job's lease from a background thread."""

    def __init__(self, job_id: str, token: datetime) -> None:
        self._job_id = job_id
        self._token = token
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._beat, name=f"lease-{job_id}", daemon=True)

    def __enter__(self) -> _LeaseHeartbeat:
        self._thread.start()
        return self

    def __exit__(self, *_exc: object) -> None:
        self._stop.set()
        # Bounded: a renewal stuck on the network must not hold up the outcome,
        # and one that lands late is refused once the outcome is written.
        self._thread.join(timeout=settings.TRAINING_HEARTBEAT_SECONDS)

    def _beat(self) -> None:
        held = True
        while not self._stop.wait(settings.TRAINING_HEARTBEAT_SECONDS):
            try:
                renewed = jobs.renew_lease(self._job_id, self._token, jobs.utcnow())
            except SQLAlchemyError:
                logger.warning("could not renew the lease on training job %s", self._job_id, exc_info=True)
                continue
            if held and not renewed:
                logger.error(
                    "training job %s lost its lease; its outcome is recorded only if no other worker claimed it",
                    self._job_id,
                )
            held = renewed
