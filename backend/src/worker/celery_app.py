"""Celery application for durable background work, brokered by Redis.

A message is acknowledged only after its task returns (task_acks_late), a
message whose worker process dies goes back on the queue
(task_reject_on_worker_lost), and Redis redelivers an unacknowledged message
only after visibility_timeout, which outlasts the longest task. Redelivery means
a task can arrive more than once, so every task claims its row in
background_jobs before doing any work (src/worker/jobs.py).

Start the worker from backend/, with Redis running:

    celery -A src.worker.celery_app worker --queues training --concurrency 1 --loglevel INFO
"""

from __future__ import annotations

import logging
import os
import sys

from celery import Celery
from celery.signals import worker_init, worker_process_init
from kombu import Exchange, Queue

from src.config.settings import settings

logger = logging.getLogger("worker")

#: Native libraries that must not be imported before the pool forks. torch,
#: XGBoost and GDAL all start threads or register state that a fork copies into
#: an unusable condition; on macOS the children then die with SIGSEGV on every
#: task, which reads like a broken queue rather than a bad import.
FORK_UNSAFE_MODULES = ("torch", "xgboost", "rasterio", "shap", "mlflow")

#: The queue POST /train publishes to. Run one worker process on it: two
#: trainings at once would write the same model file.
TRAINING_QUEUE = "training"

#: Registered name of src.worker.tasks.train_prospectivity_model.
TRAIN_TASK = "bakufu.train_prospectivity_model"

celery_app = Celery("bakufu", broker=settings.CELERY_BROKER_URL, include=["src.worker.tasks"])

celery_app.conf.update(
    # A message carries a job id and nothing else; JSON keeps pickle off the wire.
    task_serializer="json",
    accept_content=["json"],
    # Outcomes are written to background_jobs, so there is no result backend.
    task_ignore_result=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    # A task that raised or hit its time limit has already recorded the failure.
    task_acks_on_failure_or_timeout=True,
    # Reserve one message at a time, so a long run never holds messages another
    # worker could take.
    worker_prefetch_multiplier=1,
    # A fresh process for every task hands torch and XGBoost memory back.
    worker_max_tasks_per_child=1,
    # Let a run survive a broker blip: the job row, not the message, decides
    # whether a redelivered copy trains, so cancelling would only lose the work.
    worker_cancel_long_running_tasks_on_connection_loss=False,
    task_queues=(
        Queue(
            TRAINING_QUEUE,
            Exchange(TRAINING_QUEUE, type="direct"),
            routing_key=TRAINING_QUEUE,
            durable=True,
        ),
    ),
    task_routes={TRAIN_TASK: {"queue": TRAINING_QUEUE, "routing_key": TRAINING_QUEUE}},
    broker_connection_retry_on_startup=True,
    broker_transport_options={
        # Beyond the hard time limit, or Redis would hand a task that is still
        # running to a second worker.
        "visibility_timeout": settings.TRAINING_TIME_LIMIT_SECONDS + 30 * 60,
        "socket_connect_timeout": 5,
    },
    # Bounded, so POST /train answers promptly when Redis is down.
    task_publish_retry=True,
    task_publish_retry_policy={
        "max_retries": 2,
        "interval_start": 0,
        "interval_step": 0.5,
        "interval_max": 1,
    },
    enable_utc=True,
    timezone="UTC",
)


class UnsafeWorkerStart(RuntimeError):
    """The worker would fork into children that cannot run. Refuse to start."""


def _uses_prefork(sender: object) -> bool:
    pool = getattr(sender, "pool_cls", None) or getattr(getattr(sender, "app", None), "conf", None)
    name = getattr(pool, "__module__", "") + " " + str(getattr(pool, "__name__", pool))
    if "prefork" in name:
        return True
    if "solo" in name or "thread" in name or "gevent" in name or "eventlet" in name:
        return False
    # Nothing conclusive: the default pool is prefork, so assume the risky one.
    return True


def check_fork_safety(sender: object | None = None) -> None:
    """Fail closed on a prefork worker that cannot fork usable children.

    Two ways that happens, both of which end as a crash loop of children that
    die before running anything, which reads like a broken queue:
      - a native library (torch, XGBoost, GDAL) was imported in the parent;
      - macOS refuses to fork a process that touched the Objective-C runtime
        unless OBJC_DISABLE_INITIALIZE_FORK_SAFETY is set.
    """
    if sender is not None and not _uses_prefork(sender):
        return
    loaded = [name for name in FORK_UNSAFE_MODULES if name in sys.modules]
    if loaded:
        raise UnsafeWorkerStart(
            f"{', '.join(loaded)} are imported in the worker parent; with the prefork pool its "
            "children die before running a task. Import them inside the task, or start the "
            "worker with --pool solo."
        )
    if sys.platform == "darwin" and not os.environ.get("OBJC_DISABLE_INITIALIZE_FORK_SAFETY"):
        raise UnsafeWorkerStart(
            "macOS aborts forked children of a process that touched the Objective-C runtime. "
            "Start the worker as: OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES celery -A "
            "src.worker.celery_app worker --queues training --concurrency 1 (or use --pool solo)."
        )


@worker_init.connect
def _refuse_unsafe_start(sender: object = None, **_kwargs: object) -> None:
    check_fork_safety(sender)


@worker_process_init.connect
def _fresh_database_pool(**_kwargs: object) -> None:
    """Give each forked worker process database connections of its own."""
    from src.db.session import dispose_engine_after_fork

    dispose_engine_after_fork()
