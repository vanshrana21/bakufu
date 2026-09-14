"""Prospectivity prediction endpoints (Phase 2)."""

from __future__ import annotations

import traceback
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from geoalchemy2.shape import from_shape
from shapely.geometry import box
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from src.api.deps import get_db, get_optional_db
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
from src.data.masks.registry import VALID_MASKS, apply_mask, describe as describe_masks
from src.db.models import Prediction

router = APIRouter(tags=["predictions"])

#: Half-width of the cell polygon stored for a point prediction, in degrees
#: (~30 m, half of the 60 m grid the model reasons at).
_CELL_HALF_DEG = 0.00027

#: In-process registry of background training tasks. Deliberately not Celery -
#: Phase 2 keeps the dependency surface small.
_TRAIN_TASKS: dict[str, dict[str, Any]] = {}


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
    except FileNotFoundError as exc:
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
        except SQLAlchemyError:
            db.rollback()

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


def _run_training(task_id: str) -> None:
    """Background training job. Records terminal state in _TRAIN_TASKS."""
    from src.models.prospectivity.train_pu_xgboost import main as train_main

    task = _TRAIN_TASKS[task_id]
    task["status"] = "running"
    task["started_at"] = datetime.now(UTC)
    try:
        train_main()
        task["status"] = "completed"
        task["detail"] = "model retrained and saved"
    except Exception as exc:  # noqa: BLE001 - surfaced through the status endpoint
        task["status"] = "failed"
        task["detail"] = f"{type(exc).__name__}: {exc}"
        task["traceback"] = traceback.format_exc()
    finally:
        task["finished_at"] = datetime.now(UTC)


@router.post("/train", response_model=TrainTaskOut, status_code=202, summary="Retrain in background")
def start_training(background_tasks: BackgroundTasks) -> TrainTaskOut:
    task_id = uuid.uuid4().hex
    _TRAIN_TASKS[task_id] = {"status": "queued", "started_at": None, "finished_at": None}
    background_tasks.add_task(_run_training, task_id)
    return TrainTaskOut(
        task_id=task_id,
        status="started",
        detail="training runs in-process; poll GET /train/{task_id}",
    )


@router.get("/train/{task_id}", response_model=TrainStatusOut, summary="Background training status")
def training_status(task_id: str) -> TrainStatusOut:
    task = _TRAIN_TASKS.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"task {task_id} not found")
    return TrainStatusOut(
        task_id=task_id,
        status=task["status"],
        started_at=task.get("started_at"),
        finished_at=task.get("finished_at"),
        detail=task.get("detail"),
    )
