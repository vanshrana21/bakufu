"""Prospectivity prediction endpoints (Phase 2)."""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from geoalchemy2.shape import from_shape
from shapely.geometry import box
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from src.api.deps import get_db, get_optional_db
from src.api.errors import DataNotLoaded, TrainingInProgress
from src.api.schemas import (
    MaskInfoOut,
    PredictBboxIn,
    PredictBboxOut,
    PredictionRecordOut,
    PredictPointIn,
    PredictPointOut,
    TrainStatusOut,
    TrainTaskOut,
)
from src.data.masks.registry import VALID_MASKS, apply_mask
from src.data.masks.registry import describe as describe_masks
from src.db.models import BackgroundJob, Prediction
from src.worker import jobs
from src.worker.celery_app import TRAIN_TASK
from src.worker.jobs import TRAIN_TASK_NAME

logger = logging.getLogger("api.predictions")

router = APIRouter(tags=["predictions"])

#: Half-width of the cell polygon stored for a point prediction, in degrees
#: (~30 m, half of the 60 m grid the model reasons at).
_CELL_HALF_DEG = 0.00027


def _model_unavailable(exc: FileNotFoundError) -> HTTPException:
    return HTTPException(
        status_code=503,
        detail=(
            f"{exc} - the prospectivity model has not been trained yet. "
            "POST /train, or run python -m src.models.prospectivity.train_pu_xgboost"
        ),
    )


@router.post("/predict/point", response_model=PredictPointOut, summary="Score one location")
def predict_point_endpoint(
    body: PredictPointIn,
    mask: str = Query(
        "none",
        description=f"Geological post-filter to apply. One of {', '.join(VALID_MASKS)}.",
    ),
    db: Session | None = Depends(get_optional_db),
) -> PredictPointOut:
    # Imported lazily: loading torch/shap at module import would slow every
    # request path, including the endpoints that never touch the model.
    from src.models.prospectivity.predict import SCORE_CAP, predict_point

    if mask not in VALID_MASKS:
        raise HTTPException(
            status_code=422,
            detail=f"unknown mask {mask!r}; expected one of {', '.join(VALID_MASKS)}",
        )

    try:
        result = predict_point(body.lat, body.lon)
    except (FileNotFoundError, RuntimeError) as exc:
        raise _model_unavailable(exc) from exc

    if result is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"({body.lat}, {body.lon}) falls outside the available imagery "
                "footprint, so no features could be extracted."
            ),
        )

    # Mask sits between the Elkan-Noto adjustment and the cap, so a surviving
    # score is capped exactly as an unmasked one would be.
    raw_score = float(result["prospectivity_score"])
    masked_score, decision = apply_mask(body.lat, body.lon, raw_score, mask)
    final_score = min(max(masked_score, 0.0), SCORE_CAP)
    result["prospectivity_score"] = final_score

    cell = box(
        body.lon - _CELL_HALF_DEG,
        body.lat - _CELL_HALF_DEG,
        body.lon + _CELL_HALF_DEG,
        body.lat + _CELL_HALF_DEG,
    )
    # Persistence is an audit trail, not the answer: the score above came from
    # local rasters and a local model, so an unreachable database costs the
    # caller the row id and nothing else - `prediction_id` is already nullable.
    prediction_id: int | None = None
    if db is not None:
        record = Prediction(
            geom=from_shape(cell, srid=4326),
            prospectivity_score=final_score,
            deposit_type=result["predicted_type"],
            uncertainty=result["uncertainty"],
            model_version=result["model_version"],
            mask_applied=mask,
            raw_score=min(max(raw_score, 0.0), SCORE_CAP),
            final_score=final_score,
        )
        try:
            db.add(record)
            db.commit()
            db.refresh(record)
            prediction_id = record.id
        except (SQLAlchemyError, RuntimeError) as exc:
            db.rollback()
            logger.exception("could not persist prediction for model version %s", result["model_version"])
            raise HTTPException(
                status_code=503,
                detail="Prediction computed, but its audit record could not be persisted. Retry the request.",
            ) from exc

    return PredictPointOut(
        **result,
        prediction_id=prediction_id,
        mask_applied=mask,
        mask_decision=decision,
        raw_score=min(max(raw_score, 0.0), SCORE_CAP),
        final_score=final_score,
    )


@router.post("/predict/bbox", response_model=PredictBboxOut, summary="Score a grid over a bbox")
def predict_bbox_endpoint(
    body: PredictBboxIn,
    mask: str = Query(
        "none",
        description=f"Geological post-filter to apply. One of {', '.join(VALID_MASKS)}.",
    ),
) -> PredictBboxOut:
    from src.models.prospectivity.predict import SCORE_CAP, predict_bbox

    if mask not in VALID_MASKS:
        raise HTTPException(
            status_code=422,
            detail=f"unknown mask {mask!r}; expected one of {', '.join(VALID_MASKS)}",
        )

    if body.min_lon >= body.max_lon or body.min_lat >= body.max_lat:
        raise HTTPException(status_code=422, detail="min_lon/min_lat must be less than max_lon/max_lat")

    try:
        result = predict_bbox(
            body.min_lon, body.min_lat, body.max_lon, body.max_lat, body.grid_resolution_m
        )
    except FileNotFoundError as exc:
        raise _model_unavailable(exc) from exc

    if mask != "none":
        kept = 0
        for cell in result["predictions"]:
            raw = float(cell["score"])
            masked, decision = apply_mask(cell["lat"], cell["lon"], raw, mask)
            cell["raw_score"] = min(max(raw, 0.0), SCORE_CAP)
            cell["score"] = min(max(masked, 0.0), SCORE_CAP)
            cell["mask_decision"] = decision
            kept += int(masked > 0.0)
        result["predictions"].sort(key=lambda c: c["score"], reverse=True)
        result["cells_kept_by_mask"] = kept
    result["mask_applied"] = mask

    return PredictBboxOut(**result)


@router.get("/masks", response_model=list[MaskInfoOut], summary="List available prediction masks")
def list_masks() -> list[MaskInfoOut]:
    return [MaskInfoOut(**entry) for entry in describe_masks()]


@router.get(
    "/predictions/{prediction_id}",
    response_model=PredictionRecordOut,
    summary="Retrieve a stored prediction",
)
def get_prediction(prediction_id: int, db: Session = Depends(get_db)) -> PredictionRecordOut:
    row = db.get(Prediction, prediction_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"prediction {prediction_id} not found")
    return PredictionRecordOut.model_validate(row)


def _training_in_progress(job_id: str | None, status: str | None) -> TrainingInProgress:
    if job_id is None:
        return TrainingInProgress(
            detail="a training job is already in progress",
            remedy="poll GET /train/{task_id} for it, then POST /train again once it has finished",
        )
    return TrainingInProgress(
        detail=f"a training job is already in progress: {job_id} is {status}",
        remedy=f"poll GET /train/{job_id}, then POST /train again once it has finished",
    )


@router.post(
    "/train",
    response_model=TrainTaskOut,
    status_code=202,
    summary="Queue a retraining job for the Celery worker",
    responses={
        409: {"description": "A training job is already queued or running"},
        503: {"description": "The task broker is unreachable, so nothing was queued"},
    },
)
def start_training(db: Session = Depends(get_db)) -> TrainTaskOut:
    """Queue one training run.

    Training happens in a Celery worker, not in this process: an API restart,
    or the request itself going away, no longer takes the run with it. At most
    one job may be queued or running at a time - a second concurrent training
    would fight the first for the model file - so this answers 409 while one is
    active.
    """
    job_id = uuid.uuid4().hex
    now = jobs.utcnow()
    try:
        # One transaction from the lock to the insert: the advisory lock makes
        # the count below and the insert atomic against every other POST /train.
        jobs.lock_task_starts(db, TRAIN_TASK_NAME)
        jobs.expire_stale_jobs(db, TRAIN_TASK_NAME, now)
        if jobs.count_active_jobs(db, TRAIN_TASK_NAME) > 0:
            active = jobs.active_job(db, TRAIN_TASK_NAME)
            conflict = _training_in_progress(
                active.job_id if active else None, active.status if active else None
            )
            db.commit()  # keep the expiries; the lock is released with them
            raise conflict
        db.add(
            BackgroundJob(
                job_id=job_id,
                task_name=TRAIN_TASK_NAME,
                status="queued",
                created_at=now,
                updated_at=now,
            )
        )
        jobs.add_delivery(
            db,
            job_id,
            TRAIN_TASK,
            {"job_id": job_id},
        )
        db.commit()
    except IntegrityError as exc:
        # The partial unique index caught a start the advisory lock did not.
        db.rollback()
        raise _training_in_progress(None, None) from exc
    except (SQLAlchemyError, RuntimeError) as exc:
        db.rollback()
        raise DataNotLoaded(
            detail=f"could not record the training job: {type(exc).__name__}",
            remedy=(
                "run python -m scripts.migrations.add_background_jobs to bring "
                "background_jobs up to date"
            ),
        ) from exc

    return TrainTaskOut(
        task_id=job_id,
        status="queued",
        detail="queued for the Celery training worker; poll GET /train/{task_id}",
    )


@router.get("/train/{task_id}", response_model=TrainStatusOut, summary="Background training status")
def training_status(task_id: str, db: Session = Depends(get_db)) -> TrainStatusOut:
    # Expire first, so a job whose worker died reads as failed here instead of
    # running for ever.
    try:
        jobs.expire_stale_jobs(db, TRAIN_TASK_NAME, jobs.utcnow())
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        logger.warning("could not expire stale training jobs", exc_info=True)

    job = db.scalars(
        select(BackgroundJob).where(
            BackgroundJob.job_id == task_id, BackgroundJob.task_name == TRAIN_TASK_NAME
        )
    ).first()
    if job is None:
        raise HTTPException(status_code=404, detail=f"task {task_id} not found")

    detail = None
    if job.status == "completed" and job.result_data:
        detail = job.result_data.get("detail")
    elif job.status == "failed":
        detail = job.error_message

    return TrainStatusOut(
        task_id=task_id,
        status=job.status,
        started_at=job.started_at,
        finished_at=job.finished_at,
        detail=detail,
    )
