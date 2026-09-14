"""Borehole endpoints."""

from __future__ import annotations

from typing import Any

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query
from geoalchemy2.functions import ST_X, ST_Y
from sqlalchemy import Row, select
from sqlalchemy.orm import Session

from src.api.deps import get_db
from src.api.schemas import BoreholeOut, FeatureOut
from src.data.preprocess.compute_indices import INDEX_COLUMNS, add_indices
from src.data.preprocess.extract_features import FEATURE_COLUMNS, extract_features_bulk
from src.db.models import Borehole

router = APIRouter(prefix="/boreholes", tags=["boreholes"])

_COLUMNS = (
    Borehole.id,
    Borehole.nuid,
    Borehole.borehole_no,
    Borehole.block_name,
    Borehole.district,
    Borehole.state,
    Borehole.length_m,
    Borehole.rl_collar_m,
    Borehole.rl_bottom_m,
    Borehole.borehole_type,
    Borehole.start_date,
    Borehole.end_date,
    Borehole.commodity,
    Borehole.source,
    ST_X(Borehole.geom).label("lon"),
    ST_Y(Borehole.geom).label("lat"),
)


def _to_out(row: Row[Any]) -> BoreholeOut:
    return BoreholeOut.model_validate(dict(row._mapping))


@router.get("", response_model=list[BoreholeOut], summary="List boreholes")
def list_boreholes(
    block: str | None = Query(None, description="Filter by block_name (case-insensitive)"),
    district: str | None = Query(None, description="Filter by district (case-insensitive)"),
    limit: int = Query(500, ge=1, le=5000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> list[BoreholeOut]:
    stmt = select(*_COLUMNS)
    if block:
        stmt = stmt.where(Borehole.block_name.ilike(block))
    if district:
        stmt = stmt.where(Borehole.district.ilike(district))
    stmt = stmt.order_by(Borehole.id).limit(limit).offset(offset)
    return [_to_out(row) for row in db.execute(stmt)]


@router.get("/{borehole_id}", response_model=BoreholeOut, summary="Get one borehole")
def get_borehole(borehole_id: int, db: Session = Depends(get_db)) -> BoreholeOut:
    row = db.execute(select(*_COLUMNS).where(Borehole.id == borehole_id)).first()
    if row is None:
        raise HTTPException(status_code=404, detail=f"borehole {borehole_id} not found")
    return _to_out(row)


@router.get(
    "/{borehole_id}/features",
    response_model=FeatureOut,
    summary="Sample raster features at a borehole",
)
def get_borehole_features(borehole_id: int, db: Session = Depends(get_db)) -> FeatureOut:
    row = db.execute(
        select(
            Borehole.id, Borehole.borehole_no, ST_X(Borehole.geom).label("lon"),
            ST_Y(Borehole.geom).label("lat")
        ).where(Borehole.id == borehole_id)
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail=f"borehole {borehole_id} not found")

    frame = pd.DataFrame([{"lon": float(row.lon), "lat": float(row.lat)}])
    extracted = add_indices(extract_features_bulk(frame))
    record = extracted.iloc[0]

    features = {
        column: (None if pd.isna(record[column]) else float(record[column]))
        for column in FEATURE_COLUMNS + INDEX_COLUMNS
    }
    return FeatureOut(
        borehole_id=row.id,
        borehole_no=row.borehole_no,
        lat=float(row.lat),
        lon=float(row.lon),
        features=features,
    )
