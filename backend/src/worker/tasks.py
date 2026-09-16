"""Celery tasks. Run them with:

    celery -A src.worker.celery_app worker --queues training --concurrency 1 --loglevel INFO
"""

from __future__ import annotations

import logging
import os
import threading
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any

from celery import Task
from sqlalchemy.exc import SQLAlchemyError

from src.config.settings import settings
from src.worker import jobs
from src.worker.celery_app import TRAIN_TASK, celery_app

logger = logging.getLogger("worker.training")

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

    run_training_job(job_id, claim.token)
    return "claimed"


class LeaseLost(RuntimeError):
    """Raised when a job's lease lapsed before its model could be promoted."""


def run_training_job(job_id: str, token: datetime) -> None:
    """Train while renewing the job's lease, then record how it went."""
    with _LeaseHeartbeat(job_id, token):
        try:
            model_path = _train(job_id, token)
        except Exception as exc:  # noqa: BLE001 - surfaced through GET /train/{task_id}
            outcome: dict[str, Any] = {
                "status": "failed",
                "error_message": f"{type(exc).__name__}: {exc}\n{traceback.format_exc()}",
            }
        else:
            outcome = {
                "status": "completed",
                "progress": 100.0,
                "result_data": {"detail": "model retrained and saved", "model_path": str(model_path)},
            }
    _record_outcome(job_id, token, outcome)


def _train(job_id: str, token: datetime) -> Path:
    """Train into a staging file and promote it only while the lease still holds.

    Two runs can overlap - a worker cut off from the database keeps training
    while its replacement starts - and the loser must not land its model on top
    of the winner's. Training therefore writes to a file of its own, the lease
    is re-checked, and the promotion is a rename, which is atomic: the served
    path is never a half-written bundle and never the stale run's work.
    """
    # Imported here, inside the forked worker process: torch and XGBoost must
    # not start their thread pools in the parent that does the forking.
    from src.models.prospectivity.pu_xgboost import MODEL_PATH
    from src.models.prospectivity.train_pu_xgboost import main as train_main

    staging = MODEL_PATH.with_name(f".{MODEL_PATH.stem}.{job_id}.staging.pkl")
    try:
        # An explicit argv: the parser would otherwise read the worker's own
        # command line and exit.
        train_main([], save_path=staging)
        if not jobs.renew_lease(job_id, token, jobs.utcnow()):
            raise LeaseLost(
                f"the lease lapsed while job {job_id} was training, so another worker owns it now; "
                f"the new model was discarded rather than written over {MODEL_PATH.name}"
            )
        os.replace(staging, MODEL_PATH)
    finally:
        staging.unlink(missing_ok=True)
    return MODEL_PATH


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
