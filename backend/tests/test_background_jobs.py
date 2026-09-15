"""POST /train and GET /train/{task_id} against a persistent BackgroundJob row.

Runs on an in-memory SQLite database holding only the background_jobs table, so
it needs no DATABASE_URL and never writes to the real database. Training itself
is replaced by a stub: these tests pin the job lifecycle, not the model.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import src.models.prospectivity.train_pu_xgboost as train_module
from src.api.deps import get_db
from src.api.main import app
from src.db import session as db_session
from src.db.models import BackgroundJob, Base


@pytest.fixture()
def job_client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    BackgroundJob.__table__.create(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    def override_get_db() -> Iterator[Session]:
        with factory() as session:
            yield session

    monkeypatch.setattr(db_session, "SessionLocal", factory)
    app.dependency_overrides[get_db] = override_get_db
    try:
        # No `with`: the lifespan (artifact loading, warming) is not needed here.
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


def test_background_jobs_table_is_part_of_the_schema() -> None:
    """init_db's create_all builds every table in Base.metadata."""
    assert "background_jobs" in Base.metadata.tables


def test_training_job_records_success(job_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[bool] = []
    monkeypatch.setattr(train_module, "main", lambda: calls.append(True))

    started = job_client.post("/train")
    assert started.status_code == 202
    task_id = started.json()["task_id"]

    # TestClient runs background tasks before returning the response.
    status = job_client.get(f"/train/{task_id}").json()
    assert calls == [True]
    assert status["status"] == "completed"
    assert status["detail"] == "model retrained and saved"
    assert status["started_at"] is not None and status["finished_at"] is not None
    assert status["started_at"] <= status["finished_at"]


def test_training_job_records_failure(job_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    def broken() -> None:
        raise RuntimeError("raster missing")

    monkeypatch.setattr(train_module, "main", broken)

    task_id = job_client.post("/train").json()["task_id"]
    status = job_client.get(f"/train/{task_id}").json()
    assert status["status"] == "failed"
    assert "RuntimeError: raster missing" in status["detail"]
    assert status["finished_at"] is not None


def test_unknown_training_job_is_404(job_client: TestClient) -> None:
    assert job_client.get("/train/does-not-exist").status_code == 404
