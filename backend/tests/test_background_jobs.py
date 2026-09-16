"""POST /train, GET /train/{task_id}, and the durable Celery training task.

Everything here runs on a SQLite database holding only background_jobs, so it
needs neither DATABASE_URL nor Redis and never touches the real database, the
real broker or the real model. Publishing is replaced by a recorder - or, in one
test, by an in-process Celery worker on the memory transport - and training
itself by a stub: these tests pin the job lifecycle, not the model.
"""

from __future__ import annotations

import json
import time
import uuid
from collections.abc import Iterator
from datetime import timedelta
from pathlib import Path
from typing import Any

import joblib
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
from src.worker.celery_app import TRAIN_TASK, TRAINING_QUEUE, celery_app
from src.worker.tasks import train_prospectivity_model

TASK = jobs.TRAIN_TASK_NAME


@pytest.fixture()
def factory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[sessionmaker[Session]]:
    """A file-backed SQLite database: worker threads get their own connections."""
    engine = create_engine(f"sqlite:///{tmp_path / 'jobs.db'}", connect_args={"timeout": 30})
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
def trains(store: Path, monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Replaces the real training run, writing a bundle where it is told."""
    import joblib

    calls: list[str] = []

    def fake_main(argv: Any = None, save_path: Path | None = None, metrics_path: Path | None = None) -> Path:
        # The worker passes its own argv and a staging path; the process argv
        # belongs to Celery, and no published version is ever written over.
        assert argv == [] and save_path is not None and metrics_path is not None
        joblib.dump(_bundle("trained"), save_path)
        metrics_path.write_text(json.dumps(GOOD_METRICS), encoding="utf-8")
        calls.append("trained")
        return save_path

    monkeypatch.setattr(train_module, "main", fake_main)
    return calls


def _insert(factory: sessionmaker[Session], **fields: Any) -> str:
    defaults: dict[str, Any] = {
        "job_id": uuid.uuid4().hex,
        "task_name": TASK,
        "status": "queued",
        "claim_fence": 0,
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


def test_concurrent_starts_create_exactly_one_active_job(
    client: TestClient, factory: sessionmaker[Session], published: list[dict[str, Any]]
) -> None:
    """Mandatory 1: the guard has to hold when the requests arrive together."""
    import threading

    codes: list[int] = []
    barrier = threading.Barrier(8)

    def start() -> None:
        barrier.wait()
        codes.append(client.post("/train").status_code)

    threads = [threading.Thread(target=start) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    with factory() as db:
        rows = db.scalars(select(BackgroundJob)).all()
        active = [row for row in rows if row.status in jobs.ACTIVE_STATUSES]
    assert codes.count(202) == 1, f"{codes.count(202)} starts were accepted: {codes}"
    assert sorted(set(codes) - {202}) == [409], f"unexpected statuses: {sorted(set(codes))}"
    assert len(active) == 1 and len(rows) == 1
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
    client: TestClient, factory: sessionmaker[Session], store: Path, trains: list[str],
    monkeypatch: pytest.MonkeyPatch,
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
    # A broker can accept a message and still fail the acknowledgement, so the
    # job stays claimable rather than being discarded on a maybe.
    assert job.status == "queued"
    assert "did not confirm the publish" in (job.error_message or "")
    assert job.finished_at is None
    assert job.job_id in body["detail"]

    # A worker that did receive the message runs it normally.
    assert train_prospectivity_model.apply(args=(job.job_id,)).get() == "claimed"
    assert _row(factory, job.job_id).status == "completed"


def test_a_job_no_worker_received_is_failed_by_the_queue_timeout(
    client: TestClient, factory: sessionmaker[Session], store: Path, trains: list[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The other half of an unconfirmed publish: nothing picked it up."""
    def refuse(*_args: Any, **_kwargs: Any) -> None:
        raise OperationalError("Error 61 connecting to 127.0.0.1:6379. Connection refused.")

    monkeypatch.setattr(train_prospectivity_model, "apply_async", refuse)
    refused = client.post("/train")
    assert refused.status_code == 503

    with factory() as db:
        row = db.scalars(select(BackgroundJob)).one()
        stranded = row.job_id
        row.created_at = jobs.utcnow() - timedelta(seconds=settings.TRAINING_QUEUE_TIMEOUT_SECONDS + 60)
        db.commit()

    status = client.get(f"/train/{stranded}").json()
    assert status["status"] == "failed"
    assert "no worker claimed this job" in status["detail"]


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
    assert status["detail"].startswith("model retrained and published as ")
    assert status["started_at"] is not None and status["finished_at"] is not None
    assert status["started_at"] <= status["finished_at"]


def test_the_worker_records_a_training_failure(
    client: TestClient, factory: sessionmaker[Session], published: list[dict[str, Any]],
    store: Path, monkeypatch: pytest.MonkeyPatch,
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
    factory: sessionmaker[Session], store: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "TRAINING_HEARTBEAT_SECONDS", 0.05)
    renewals: list[bool] = []
    real_renew = jobs.renew_lease

    def spy(*args: Any, **kwargs: Any) -> bool:
        renewed = real_renew(*args, **kwargs)
        renewals.append(renewed)
        return renewed

    monkeypatch.setattr(jobs, "renew_lease", spy)

    def slow_training(argv: Any = None, save_path: Path | None = None, metrics_path: Path | None = None) -> Path:
        time.sleep(0.3)
        assert save_path is not None and metrics_path is not None
        joblib.dump(_bundle("slow"), save_path)
        metrics_path.write_text(json.dumps(GOOD_METRICS), encoding="utf-8")
        return save_path

    monkeypatch.setattr(train_module, "main", slow_training)
    _insert(factory, job_id="slow", status="queued")

    train_prospectivity_model.apply(args=("slow",)).get()

    assert len(renewals) >= 2 and all(renewals)
    assert _row(factory, "slow").status == "completed"


# --- the model artifact --------------------------------------------------


@pytest.fixture()
def store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A registry of its own, so no test can promote into models/."""
    from src.models import registry

    root = tmp_path / "registry"
    monkeypatch.setattr(registry, "REGISTRY_DIR", root)
    monkeypatch.setattr(registry, "VERSIONS_DIR", root / "versions")
    monkeypatch.setattr(registry, "STAGING_DIR", root / "staging")
    monkeypatch.setattr(registry, "POINTER_PATH", root / "active.json")
    monkeypatch.setattr(registry, "LOCK_PATH", root / ".registry.lock")
    registry.clear_pointer_cache()
    yield root
    registry.clear_pointer_cache()


def _serving_features() -> list[str]:
    """The feature list the active model takes, which a candidate has to match."""
    from src.models.prospectivity import predict

    if predict.SHIPPED_MODEL_PATH.exists():
        return list(joblib.load(predict.SHIPPED_MODEL_PATH)["features"])
    return ["b11", "b12"]


def _bundle(marker: str) -> dict[str, Any]:
    return {"model": marker, "features": _serving_features(), "elkan_noto_c": 0.8}


#: Fold metrics a candidate passes the acceptance checks with.
GOOD_METRICS: dict[str, Any] = {
    "folds": [{"auc": 0.71, "auc_pr": 0.24, "n_test": 100, "n_test_pos": 5}]
}


def _stub_training(monkeypatch: pytest.MonkeyPatch, during: Any = None, marker: str = "trained") -> list[Path]:
    """Replace training with a valid bundle written where it is told."""
    import joblib

    staged: list[Path] = []

    def fake_main(argv: Any = None, save_path: Path | None = None, metrics_path: Path | None = None) -> Path:
        # The worker must pass its own argv; the process's belongs to Celery.
        assert argv == [] and save_path is not None and metrics_path is not None
        joblib.dump(_bundle(marker), save_path)
        metrics_path.write_text(
            json.dumps({"version": save_path.parent.name, **GOOD_METRICS}), encoding="utf-8"
        )
        staged.append(save_path)
        if during is not None:
            during()
        return save_path

    monkeypatch.setattr(train_module, "main", fake_main)
    return staged


def test_a_finished_run_publishes_a_version_without_touching_the_served_model(
    factory: sessionmaker[Session], store: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from src.models import registry
    from src.models.prospectivity import predict

    monkeypatch.delenv("PROSPECTIVITY_MODEL", raising=False)
    monkeypatch.setattr(settings, "TRAINING_ACTIVATE_ON_SUCCESS", False)
    staged = _stub_training(monkeypatch)
    _insert(factory, job_id="publishes", status="queued")

    assert train_prospectivity_model.apply(args=("publishes",)).get() == "claimed"

    job = _row(factory, "publishes")
    assert job.status == "completed"
    assert job.result_data["activated"] is False
    version = job.result_data["version"]
    assert version in registry.versions()
    assert joblib.load(registry.version_dir(version) / registry.MODEL_FILENAME)["model"] == "trained"
    # Publishing alone must not change what inference loads.
    assert predict.active_model_path() == predict.SHIPPED_MODEL_PATH
    assert not staged[0].parent.exists(), "the staging directory was left behind"


def test_a_finished_run_changes_what_is_served_when_activation_is_on(
    factory: sessionmaker[Session], store: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Mandatory 6: the artifact predict_point and the heatmap key actually use."""
    from src.api.routers import reference
    from src.models.prospectivity import explain, predict

    monkeypatch.delenv("PROSPECTIVITY_MODEL", raising=False)
    monkeypatch.setattr(settings, "TRAINING_ACTIVATE_ON_SUCCESS", True)
    explain.clear_bundle_cache()
    _stub_training(monkeypatch, marker="the-new-model")
    before_key = reference._cache_key((79.0, 21.3, 80.6, 22.1), 32, "none", predict.active_model_version())
    _insert(factory, job_id="activates", status="queued")

    train_prospectivity_model.apply(args=("activates",)).get()

    job = _row(factory, "activates")
    assert job.result_data["activated"] is True
    assert predict.active_model_path() == Path(job.result_data["model_path"])
    assert predict.active_model_version() == job.result_data["version"]
    # What load_bundle - and so score_frame - resolves to has changed with it.
    assert explain.load_bundle(predict.active_model_path())["model"] == "the-new-model"
    after_key = reference._cache_key((79.0, 21.3, 80.6, 22.1), 32, "none", predict.active_model_version())
    assert before_key != after_key, "cached tiles would survive a promotion"


def _metrics(auc: float, auc_pr: float, base: float = 0.05) -> dict[str, Any]:
    positives = max(1, round(base * 100))
    return {"folds": [{"auc": auc, "auc_pr": auc_pr, "n_test": 100, "n_test_pos": positives}]}


def _stub_training_with(monkeypatch: pytest.MonkeyPatch, bundle: dict[str, Any], metrics: dict[str, Any]) -> None:
    def fake_main(argv: Any = None, save_path: Path | None = None, metrics_path: Path | None = None) -> Path:
        assert save_path is not None and metrics_path is not None
        joblib.dump(bundle, save_path)
        metrics_path.write_text(json.dumps(metrics), encoding="utf-8")
        return save_path

    monkeypatch.setattr(train_module, "main", fake_main)


def test_a_model_that_passes_the_checks_takes_over_serving(
    factory: sessionmaker[Session], store: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The default path: train, pass, serve. No human step in between."""
    from src.models.prospectivity import predict

    monkeypatch.delenv("PROSPECTIVITY_MODEL", raising=False)
    assert settings.TRAINING_ACTIVATE_ON_SUCCESS is True
    _stub_training_with(
        monkeypatch,
        {"model": "candidate", "features": _serving_features(), "elkan_noto_c": 0.8},
        _metrics(auc=0.72, auc_pr=0.30),
    )
    _insert(factory, job_id="good", status="queued")

    train_prospectivity_model.apply(args=("good",)).get()

    job = _row(factory, "good")
    assert job.result_data["activated"] is True, job.result_data["detail"]
    assert job.result_data["activation_blocked_by"] == []
    assert predict.active_model_path() == Path(job.result_data["model_path"])
    assert "serving now uses it" in job.result_data["detail"]


def test_a_model_no_better_than_chance_is_published_but_not_served(
    factory: sessionmaker[Session], store: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """What the v1 promotion would have needed: refuse to serve a bad model."""
    from src.models import registry
    from src.models.prospectivity import predict

    monkeypatch.delenv("PROSPECTIVITY_MODEL", raising=False)
    _stub_training_with(
        monkeypatch,
        {"model": "hopeless", "features": _serving_features(), "elkan_noto_c": 0.8},
        _metrics(auc=0.41, auc_pr=0.01),
    )
    _insert(factory, job_id="weak", status="queued")

    train_prospectivity_model.apply(args=("weak",)).get()

    job = _row(factory, "weak")
    assert job.status == "completed"
    assert job.result_data["activated"] is False
    assert any("chance" in reason for reason in job.result_data["activation_blocked_by"])
    # Published as evidence, but serving is untouched.
    assert job.result_data["version"] in registry.versions()
    assert predict.active_model_path() == predict.SHIPPED_MODEL_PATH


def test_a_model_with_a_different_feature_schema_is_not_served(
    factory: sessionmaker[Session], store: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from src.models.prospectivity import predict

    monkeypatch.delenv("PROSPECTIVITY_MODEL", raising=False)
    _stub_training_with(
        monkeypatch,
        {"model": "wrong-schema", "features": ["only", "three", "features"], "elkan_noto_c": 0.8},
        _metrics(auc=0.90, auc_pr=0.80),
    )
    _insert(factory, job_id="schema", status="queued")

    train_prospectivity_model.apply(args=("schema",)).get()

    job = _row(factory, "schema")
    assert job.result_data["activated"] is False
    assert any("features differ" in reason for reason in job.result_data["activation_blocked_by"])
    assert predict.active_model_path() == predict.SHIPPED_MODEL_PATH


def test_activation_can_still_be_switched_off(
    factory: sessionmaker[Session], store: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from src.models.prospectivity import predict

    monkeypatch.delenv("PROSPECTIVITY_MODEL", raising=False)
    monkeypatch.setattr(settings, "TRAINING_ACTIVATE_ON_SUCCESS", False)
    _stub_training(monkeypatch)
    _insert(factory, job_id="manual", status="queued")

    train_prospectivity_model.apply(args=("manual",)).get()

    job = _row(factory, "manual")
    assert job.result_data["activated"] is False
    assert "activation is switched off" in job.result_data["detail"]
    assert predict.active_model_path() == predict.SHIPPED_MODEL_PATH


def test_an_artifact_with_no_ledger_entry_is_adopted_not_retrained(
    factory: sessionmaker[Session], store: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The window between the file landing and the row being written."""
    from sqlalchemy import update as sql_update

    from src.models import registry
    from src.worker.tasks import _train_and_publish

    trained = _stub_training(monkeypatch)
    _insert(factory, job_id="orphan", status="queued")
    claim = jobs.claim_job("orphan", jobs.utcnow())
    assert claim.token is not None
    published = _train_and_publish("orphan", claim.token, claim.fence)
    # The database write that follows the publish never happened.
    with factory() as db:
        db.execute(
            sql_update(BackgroundJob).where(BackgroundJob.job_id == "orphan").values(
                artifact_version=None, artifact_sha256=None, artifact_published_at=None
            )
        )
        db.commit()

    recovered = _train_and_publish("orphan", claim.token, claim.fence)

    assert len(trained) == 1, "the artifact was retrained instead of adopted"
    assert recovered.version == published.version
    assert registry.versions() == [published.version]
    # And the ledger now has it, so the next recovery needs no search.
    assert jobs.published_artifact("orphan").version == published.version


def test_orphan_recovery_fails_if_the_claim_was_lost(
    factory: sessionmaker[Session], store: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from sqlalchemy import update as sql_update

    from src.models import registry
    from src.worker.tasks import RegistryMismatch, _train_and_publish

    _stub_training(monkeypatch)
    _insert(factory, job_id="orphan-lost", status="queued")
    claim = jobs.claim_job("orphan-lost", jobs.utcnow())
    assert claim.token is not None
    published = _train_and_publish("orphan-lost", claim.token, claim.fence)

    with factory() as db:
        db.execute(
            sql_update(BackgroundJob)
            .where(BackgroundJob.job_id == "orphan-lost")
            .values(
                artifact_version=None,
                artifact_sha256=None,
                artifact_published_at=None,
                started_at=jobs.utcnow() + timedelta(seconds=1),
            )
        )
        db.commit()

    monkeypatch.setattr(jobs, "record_publication", lambda *args, **kwargs: False)
    with pytest.raises(RegistryMismatch, match="no longer owns"):
        _train_and_publish("orphan-lost", claim.token, claim.fence)
    assert registry.version_dir(published.version).is_dir()


def test_a_worker_that_lost_its_job_publishes_nothing(
    factory: sessionmaker[Session], store: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Two runs can overlap; the one that lost the job must not publish."""
    from src.models import registry
    from src.models.prospectivity import predict

    monkeypatch.delenv("PROSPECTIVITY_MODEL", raising=False)
    monkeypatch.setattr(settings, "TRAINING_ACTIVATE_ON_SUCCESS", True)

    def taken_over() -> None:
        later = jobs.utcnow() + timedelta(seconds=settings.TRAINING_LEASE_SECONDS + 60)
        assert jobs.claim_job("handed-over", later).token is not None

    staged = _stub_training(monkeypatch, during=taken_over)
    _insert(factory, job_id="handed-over", status="queued")

    train_prospectivity_model.apply(args=("handed-over",)).get()

    assert registry.versions() == [], "a worker that lost its job published anyway"
    assert predict.active_model_path() == predict.SHIPPED_MODEL_PATH
    assert not staged[0].parent.exists()
    # The new owner still holds the job, so the loser's failure is discarded too.
    assert _row(factory, "handed-over").status == "running"


def test_every_claim_takes_a_fence_of_its_own(factory: sessionmaker[Session]) -> None:
    """The allocator must not hand two claims the same fence, even in parallel."""
    import threading

    job_ids = [_insert(factory, job_id=f"job-{index}", status="queued", task_name=f"task-{index}")
               for index in range(12)]
    fences: list[int] = []
    guard = threading.Lock()
    barrier = threading.Barrier(len(job_ids))

    def claim(job_id: str) -> None:
        barrier.wait()
        claimed = jobs.claim_job(job_id, jobs.utcnow())
        with guard:
            fences.append(claimed.fence)

    threads = [threading.Thread(target=claim, args=(job_id,)) for job_id in job_ids]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert len(fences) == len(job_ids)
    assert all(fence > 0 for fence in fences)
    assert len(set(fences)) == len(fences), f"two claims shared a fence: {sorted(fences)}"


def test_the_database_refuses_two_rows_holding_one_fence(factory: sessionmaker[Session]) -> None:
    _insert(factory, job_id="one", status="completed", task_name="task-a", claim_fence=7)
    with pytest.raises(IntegrityError):
        _insert(factory, job_id="two", status="completed", task_name="task-b", claim_fence=7)
    # Unclaimed rows all sit at 0, which the constraint deliberately ignores.
    _insert(factory, job_id="three", status="completed", task_name="task-c", claim_fence=0)
    _insert(factory, job_id="four", status="completed", task_name="task-d", claim_fence=0)


def test_publication_is_recorded_in_the_database(
    factory: sessionmaker[Session], store: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The ledger, not a directory scan, is what says a job published."""
    from src.models import registry

    monkeypatch.setattr(settings, "TRAINING_ACTIVATE_ON_SUCCESS", True)
    _stub_training(monkeypatch)
    _insert(factory, job_id="ledger", status="queued")

    train_prospectivity_model.apply(args=("ledger",)).get()

    job = _row(factory, "ledger")
    recorded = jobs.published_artifact("ledger")
    assert recorded is not None
    assert recorded.version == job.result_data["version"]
    assert recorded.sha256 == registry.sha256(Path(job.result_data["model_path"]))
    assert recorded.published_at is not None and recorded.activated_at is not None
    assert jobs.published_artifacts(TASK)[0].version == recorded.version


def test_recovery_refuses_an_artifact_the_registry_no_longer_has(
    factory: sessionmaker[Session], store: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A registry restored from a stale backup must not read as a healthy job."""
    import shutil

    from src.worker.tasks import RegistryMismatch, _train_and_publish

    _stub_training(monkeypatch)
    _insert(factory, job_id="lost", status="queued")
    claim = jobs.claim_job("lost", jobs.utcnow())
    assert claim.token is not None
    published = _train_and_publish("lost", claim.token, claim.fence)
    shutil.rmtree(published.path.parent)

    with pytest.raises(RegistryMismatch, match="missing from"):
        _train_and_publish("lost", claim.token, claim.fence)


def test_recovery_refuses_an_artifact_that_changed_on_disk(
    factory: sessionmaker[Session], store: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from src.worker.tasks import RegistryMismatch, _train_and_publish

    _stub_training(monkeypatch)
    _insert(factory, job_id="tampered", status="queued")
    claim = jobs.claim_job("tampered", jobs.utcnow())
    assert claim.token is not None
    published = _train_and_publish("tampered", claim.token, claim.fence)
    joblib.dump({"model": "swapped", "features": ["b11"], "elkan_noto_c": 0.8}, published.path)

    with pytest.raises(RegistryMismatch, match="digest"):
        _train_and_publish("tampered", claim.token, claim.fence)


def test_a_crash_after_publishing_is_recovered_without_retraining(
    factory: sessionmaker[Session], store: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Mandatory 5: the outcome is recorded on redelivery; nothing trains twice."""
    from src.models import registry

    monkeypatch.setattr(settings, "TRAINING_ACTIVATE_ON_SUCCESS", True)
    trained: list[Path] = _stub_training(monkeypatch)
    _insert(factory, job_id="crashed", status="queued")
    first_claim = jobs.claim_job("crashed", jobs.utcnow())
    assert first_claim.token is not None
    from src.worker.tasks import _train_and_publish

    published = _train_and_publish("crashed", first_claim.token, first_claim.fence)
    assert len(trained) == 1
    # ...and the worker dies here, before the outcome is written. Its lease
    # lapses, and the message is delivered again.
    with factory() as db:
        row = db.scalars(select(BackgroundJob).where(BackgroundJob.job_id == "crashed")).one()
        row.updated_at = jobs.utcnow() - timedelta(seconds=settings.TRAINING_LEASE_SECONDS + 60)
        db.commit()

    assert train_prospectivity_model.apply(args=("crashed",)).get() == "claimed"

    assert len(trained) == 1, "the redelivery retrained instead of recovering"
    assert registry.versions() == [published.version]
    job = _row(factory, "crashed")
    assert job.status == "completed"
    assert job.result_data["version"] == published.version


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
