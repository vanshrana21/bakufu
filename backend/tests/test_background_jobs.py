"""POST /train, GET /train/{task_id}, and the durable Celery training task.

Everything here runs on a SQLite database holding only background_jobs, so it
needs neither DATABASE_URL nor Redis and never touches the real database, the
real broker or the real model. Publishing is replaced by a recorder - or, in one
test, by an in-process Celery worker on the memory transport - and training
itself by a stub: these tests pin the job lifecycle, not the model.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Iterator
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from kombu.exceptions import OperationalError
from sqlalchemy import create_engine, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

import src.models.prospectivity.train_pu_xgboost as train_module
from src.api.deps import get_db
from src.api.main import app
from src.config.settings import settings
from src.db import session as db_session
from src.db.models import BackgroundJob, Base
from src.worker import jobs
from src.worker.celery_app import TRAINING_QUEUE, TRAIN_TASK, celery_app
from src.worker.tasks import train_prospectivity_model

TASK = jobs.TRAIN_TASK_NAME


@pytest.fixture()
def factory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[sessionmaker[Session]]:
    """A file-backed SQLite database: worker threads get their own connections."""
    engine = create_engine(f"sqlite:///{tmp_path / 'jobs.db'}")
    BackgroundJob.__table__.create(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(db_session, "SessionLocal", sessions)
    yield sessions
    engine.dispose()


@pytest.fixture()
def published(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    """Records what POST /train publishes, instead of sending it to Redis."""
    sent: list[dict[str, Any]] = []

    def fake_apply_async(args: tuple[Any, ...] | None = None, **options: Any) -> None:
        sent.append({"args": args, **options})

    monkeypatch.setattr(train_prospectivity_model, "apply_async", fake_apply_async)
    return sent


@pytest.fixture()
def client(factory: sessionmaker[Session], api_headers: dict[str, str]) -> Iterator[TestClient]:
    def override_get_db() -> Iterator[Session]:
        with factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    try:
        # No `with`: the lifespan (artifact loading, warming) is not needed here.
        yield TestClient(app, headers=api_headers)
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.fixture()
def trains(model_path: Path, monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Replaces the real training run, writing to the staging path it is handed."""
    calls: list[str] = []

    def fake_main(argv: Any = None, save_path: Path | None = None) -> Path:
        # The worker passes its own argv and a staging path; the process argv
        # belongs to Celery, and the served path is only written by a rename.
        assert argv == [] and save_path is not None
        save_path.write_bytes(b"a freshly trained model")
        calls.append("trained")
        return save_path

    monkeypatch.setattr(train_module, "main", fake_main)
    return calls


def _insert(factory: sessionmaker[Session], **fields: Any) -> str:
    defaults: dict[str, Any] = {
        "job_id": uuid.uuid4().hex,
        "task_name": TASK,
        "status": "queued",
        "created_at": jobs.utcnow(),
        "updated_at": jobs.utcnow(),
    }
    row = BackgroundJob(**{**defaults, **fields})
    with factory() as db:
        db.add(row)
        db.commit()
        return row.job_id


def _row(factory: sessionmaker[Session], job_id: str) -> BackgroundJob:
    with factory() as db:
        found = db.scalars(select(BackgroundJob).where(BackgroundJob.job_id == job_id)).first()
        assert found is not None
        return found


# --- schema --------------------------------------------------------------


def test_background_jobs_table_is_part_of_the_schema() -> None:
    """init_db's create_all builds every table in Base.metadata."""
    assert "background_jobs" in Base.metadata.tables


def test_the_database_allows_only_one_active_job_per_task(factory: sessionmaker[Session]) -> None:
    """The partial unique index, not just the endpoint, enforces the singleton."""
    _insert(factory, job_id="first", status="queued")
    with pytest.raises(IntegrityError):
        _insert(factory, job_id="second", status="running")
    # A finished job frees the slot, and another task keeps its own.
    _insert(factory, job_id="other-task", status="queued", task_name="something_else")
    with factory() as db:
        db.execute(select(BackgroundJob))
        first = db.scalars(select(BackgroundJob).where(BackgroundJob.job_id == "first")).one()
        first.status = "completed"
        db.commit()
    _insert(factory, job_id="third", status="queued")


# --- POST /train ---------------------------------------------------------


def test_starting_training_queues_a_job_and_publishes_it(
    client: TestClient, factory: sessionmaker[Session], published: list[dict[str, Any]]
) -> None:
    response = client.post("/train")
    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "queued"

    job = _row(factory, body["task_id"])
    assert (job.status, job.task_name, job.started_at, job.finished_at) == ("queued", TASK, None, None)
    # The Celery task id is the job id, so a job can be traced across both.
    assert published == [{"args": (body["task_id"],), "task_id": body["task_id"]}]


def test_a_second_start_is_refused_while_a_job_is_active(
    client: TestClient, published: list[dict[str, Any]]
) -> None:
    first = client.post("/train").json()["task_id"]

    conflict = client.post("/train")
    assert conflict.status_code == 409
    body = conflict.json()
    assert body["error_code"] == "training_in_progress"
    assert first in body["detail"] and "queued" in body["detail"]
    assert f"GET /train/{first}" in body["remedy"]
    assert len(published) == 1


def test_a_running_job_also_refuses_a_second_start(
    client: TestClient, factory: sessionmaker[Session], published: list[dict[str, Any]]
) -> None:
    _insert(factory, job_id="in-flight", status="running", started_at=jobs.utcnow())
    conflict = client.post("/train")
    assert conflict.status_code == 409
    assert "in-flight is running" in conflict.json()["detail"]
    assert published == []


def test_a_broker_outage_fails_the_job_instead_of_stranding_it(
    client: TestClient, factory: sessionmaker[Session], monkeypatch: pytest.MonkeyPatch
) -> None:
    def refuse(*_args: Any, **_kwargs: Any) -> None:
        raise OperationalError("Error 61 connecting to 127.0.0.1:6379. Connection refused.")

    monkeypatch.setattr(train_prospectivity_model, "apply_async", refuse)
    response = client.post("/train")
    assert response.status_code == 503
    body = response.json()
    assert body["error_code"] == "broker_unavailable"
    assert "CELERY_BROKER_URL" in body["remedy"]

    with factory() as db:
        job = db.scalars(select(BackgroundJob)).one()
    assert job.status == "failed"
    assert "never reached the task broker" in (job.error_message or "")
    assert job.finished_at is not None

    # The slot is free again: the next start is accepted.
    sent: list[Any] = []
    monkeypatch.setattr(train_prospectivity_model, "apply_async", lambda *a, **k: sent.append(a))
    assert client.post("/train").status_code == 202
    assert len(sent) == 1


def test_a_job_no_worker_claimed_stops_blocking_new_ones(
    client: TestClient, factory: sessionmaker[Session], published: list[dict[str, Any]]
) -> None:
    stale = jobs.utcnow() - timedelta(seconds=settings.TRAINING_QUEUE_TIMEOUT_SECONDS + 60)
    _insert(factory, job_id="never-claimed", status="queued", created_at=stale, updated_at=stale)

    assert client.post("/train").status_code == 202
    abandoned = _row(factory, "never-claimed")
    assert abandoned.status == "failed"
    assert "no worker claimed this job" in (abandoned.error_message or "")


def test_a_job_whose_worker_died_stops_blocking_new_ones(
    client: TestClient, factory: sessionmaker[Session], published: list[dict[str, Any]]
) -> None:
    lapsed = jobs.utcnow() - timedelta(seconds=settings.TRAINING_LEASE_SECONDS + 60)
    _insert(factory, job_id="lease-lapsed", status="running", started_at=lapsed, updated_at=lapsed)

    assert client.post("/train").status_code == 202
    abandoned = _row(factory, "lease-lapsed")
    assert abandoned.status == "failed"
    assert "stopped renewing its lease" in (abandoned.error_message or "")


# --- GET /train/{task_id} ------------------------------------------------


def test_status_reports_an_abandoned_job_as_failed(
    client: TestClient, factory: sessionmaker[Session]
) -> None:
    lapsed = jobs.utcnow() - timedelta(seconds=settings.TRAINING_LEASE_SECONDS + 60)
    _insert(factory, job_id="abandoned", status="running", started_at=lapsed, updated_at=lapsed)

    status = client.get("/train/abandoned").json()
    assert status["status"] == "failed"
    assert "stopped renewing its lease" in status["detail"]


def test_status_reports_a_queued_job_as_queued(
    client: TestClient, published: list[dict[str, Any]]
) -> None:
    task_id = client.post("/train").json()["task_id"]
    status = client.get(f"/train/{task_id}").json()
    assert status["status"] == "queued"
    assert status["started_at"] is None and status["finished_at"] is None


def test_unknown_training_job_is_404(client: TestClient) -> None:
    assert client.get("/train/does-not-exist").status_code == 404


# --- the worker task -----------------------------------------------------


def test_the_worker_trains_and_records_success(
    client: TestClient, factory: sessionmaker[Session], published: list[dict[str, Any]], trains: list[str]
) -> None:
    task_id = client.post("/train").json()["task_id"]

    assert train_prospectivity_model.apply(args=(task_id,)).get() == "claimed"

    assert trains == ["trained"]
    status = client.get(f"/train/{task_id}").json()
    assert status["status"] == "completed"
    assert status["detail"] == "model retrained and saved"
    assert status["started_at"] is not None and status["finished_at"] is not None
    assert status["started_at"] <= status["finished_at"]


def test_the_worker_records_a_training_failure(
    client: TestClient, factory: sessionmaker[Session], published: list[dict[str, Any]],
    model_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    def broken(*_args: Any, **_kwargs: Any) -> None:
        raise RuntimeError("raster missing")

    monkeypatch.setattr(train_module, "main", broken)
    task_id = client.post("/train").json()["task_id"]

    train_prospectivity_model.apply(args=(task_id,)).get()

    status = client.get(f"/train/{task_id}").json()
    assert status["status"] == "failed"
    assert "RuntimeError: raster missing" in status["detail"]
    assert status["finished_at"] is not None


def test_a_duplicate_delivery_never_trains_twice(
    factory: sessionmaker[Session], trains: list[str]
) -> None:
    _insert(factory, job_id="already-done", status="completed", finished_at=jobs.utcnow())
    assert train_prospectivity_model.apply(args=("already-done",)).get() == "completed"
    assert train_prospectivity_model.apply(args=("missing-row",)).get() == "missing"
    assert trains == []


def test_a_live_lease_defers_a_redelivered_task(
    factory: sessionmaker[Session], trains: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Another worker is still on it: come back once its lease would have lapsed."""
    _insert(factory, job_id="in-flight", status="running", started_at=jobs.utcnow())
    deferred: list[float] = []

    class Deferred(Exception):
        pass

    def fake_retry(**options: Any) -> Exception:
        deferred.append(options["countdown"])
        return Deferred()

    monkeypatch.setattr(train_prospectivity_model, "retry", fake_retry)
    with pytest.raises(Deferred):
        train_prospectivity_model("in-flight")

    assert deferred == [settings.TRAINING_LEASE_SECONDS + settings.TRAINING_HEARTBEAT_SECONDS]
    assert trains == []


def test_a_lapsed_lease_is_taken_over(factory: sessionmaker[Session], trains: list[str]) -> None:
    lapsed = jobs.utcnow() - timedelta(seconds=settings.TRAINING_LEASE_SECONDS + 60)
    _insert(factory, job_id="dead-worker", status="running", started_at=lapsed, updated_at=lapsed)

    assert train_prospectivity_model.apply(args=("dead-worker",)).get() == "claimed"

    job = _row(factory, "dead-worker")
    assert trains == ["trained"] and job.status == "completed"
    assert job.started_at is not None and job.started_at > lapsed.replace(tzinfo=None)


def test_a_worker_that_lost_its_job_cannot_overwrite_it(factory: sessionmaker[Session]) -> None:
    _insert(factory, job_id="handed-over", status="queued")
    mine = jobs.claim_job("handed-over", jobs.utcnow())
    assert mine.token is not None

    theirs = jobs.claim_job(
        "handed-over", jobs.utcnow() + timedelta(seconds=settings.TRAINING_LEASE_SECONDS + 60)
    )
    assert theirs.token is not None

    assert jobs.renew_lease("handed-over", mine.token, jobs.utcnow()) is False
    assert jobs.record_outcome("handed-over", mine.token, status="failed") is False
    assert jobs.record_outcome("handed-over", theirs.token, status="completed") is True
    assert _row(factory, "handed-over").status == "completed"


def test_the_lease_is_renewed_while_training(
    factory: sessionmaker[Session], model_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "TRAINING_HEARTBEAT_SECONDS", 0.05)
    renewals: list[bool] = []
    real_renew = jobs.renew_lease

    def spy(*args: Any, **kwargs: Any) -> bool:
        renewed = real_renew(*args, **kwargs)
        renewals.append(renewed)
        return renewed

    monkeypatch.setattr(jobs, "renew_lease", spy)

    def slow_training(argv: Any = None, save_path: Path | None = None) -> Path:
        time.sleep(0.3)
        assert save_path is not None
        save_path.write_bytes(b"a freshly trained model")
        return save_path

    monkeypatch.setattr(train_module, "main", slow_training)
    _insert(factory, job_id="slow", status="queued")

    train_prospectivity_model.apply(args=("slow",)).get()

    assert len(renewals) >= 2 and all(renewals)
    assert _row(factory, "slow").status == "completed"


# --- the model artifact --------------------------------------------------


@pytest.fixture()
def model_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Stand in for models/prospectivity_v1.pkl, with a model already in place."""
    import src.models.prospectivity.pu_xgboost as pu_xgboost

    path = tmp_path / "prospectivity_v1.pkl"
    path.write_bytes(b"the model in production")
    monkeypatch.setattr(pu_xgboost, "MODEL_PATH", path)
    return path


def _stub_training(monkeypatch: pytest.MonkeyPatch, during: Any = None) -> list[Path]:
    """Replace training with a write to whatever path it is handed."""
    staged: list[Path] = []

    def fake_main(argv: Any = None, save_path: Path | None = None) -> Path:
        # The worker must pass its own argv; the process's belongs to Celery.
        assert argv == [] and save_path is not None
        save_path.write_bytes(b"a freshly trained model")
        staged.append(save_path)
        if during is not None:
            during()
        return save_path

    monkeypatch.setattr(train_module, "main", fake_main)
    return staged


def test_a_finished_run_promotes_its_staged_model(
    factory: sessionmaker[Session], model_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    staged = _stub_training(monkeypatch)
    _insert(factory, job_id="promotes", status="queued")

    assert train_prospectivity_model.apply(args=("promotes",)).get() == "claimed"

    assert model_path.read_bytes() == b"a freshly trained model"
    assert staged and staged[0] != model_path, "training wrote straight to the served path"
    assert not staged[0].exists(), "the staging file was left behind"
    job = _row(factory, "promotes")
    assert job.status == "completed"
    assert job.result_data == {"detail": "model retrained and saved", "model_path": str(model_path)}


def test_a_worker_that_lost_its_lease_does_not_overwrite_the_model(
    factory: sessionmaker[Session], model_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Two runs can overlap; the one that lost the job must not land its model."""
    def taken_over() -> None:
        later = jobs.utcnow() + timedelta(seconds=settings.TRAINING_LEASE_SECONDS + 60)
        assert jobs.claim_job("handed-over", later).token is not None

    staged = _stub_training(monkeypatch, during=taken_over)
    _insert(factory, job_id="handed-over", status="queued")

    train_prospectivity_model.apply(args=("handed-over",)).get()

    assert model_path.read_bytes() == b"the model in production"
    assert not staged[0].exists()
    # The new owner still holds the job, so the loser's failure is discarded too.
    assert _row(factory, "handed-over").status == "running"


# --- Celery wiring -------------------------------------------------------


def test_celery_is_configured_for_durable_delivery() -> None:
    conf = celery_app.conf
    assert conf.task_acks_late is True
    assert conf.task_reject_on_worker_lost is True
    assert conf.worker_prefetch_multiplier == 1
    assert conf.accept_content == ["json"] and conf.task_serializer == "json"
    # Redis must not hand a task that is still running to a second worker.
    assert conf.broker_transport_options["visibility_timeout"] > settings.TRAINING_TIME_LIMIT_SECONDS
    assert conf.broker_url.startswith("redis://")
    assert conf.task_routes[TRAIN_TASK]["queue"] == TRAINING_QUEUE
    assert train_prospectivity_model.name == TRAIN_TASK


def test_a_real_worker_consumes_the_queued_job(
    client: TestClient, factory: sessionmaker[Session], trains: list[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """End to end through Celery itself, on the in-memory transport."""
    from celery.contrib.testing.worker import start_worker

    monkeypatch.setitem(celery_app.conf, "broker_url", "memory://")
    monkeypatch.setattr(celery_app, "_pool", None)

    with start_worker(celery_app, pool="solo", perform_ping_check=False, queues=[TRAINING_QUEUE], shutdown_timeout=30):
        task_id = client.post("/train").json()["task_id"]
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            status = client.get(f"/train/{task_id}").json()["status"]
            if status in {"completed", "failed"}:
                break
            time.sleep(0.1)

    assert status == "completed"
    assert trains == ["trained"]
