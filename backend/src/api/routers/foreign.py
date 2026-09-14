"""Foreign deposit endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from geoalchemy2.functions import ST_X, ST_Y
from sqlalchemy import Row, func, select
from sqlalchemy.orm import Session

from src.api.deps import get_db
from src.api.schemas import ForeignDepositOut, ForeignDepositPage
from src.db.models import ForeignDeposit

router = APIRouter(prefix="/foreign", tags=["foreign"])

_COLUMNS = (
    ForeignDeposit.id,
    ForeignDeposit.deposit_name,
    ForeignDeposit.country,
    ForeignDeposit.deposit_type,
    ForeignDeposit.host_rock,
    ForeignDeposit.age,
    ForeignDeposit.grade_pct,
    ForeignDeposit.tonnage,
    ForeignDeposit.source,
    ForeignDeposit.reference,
    ST_X(ForeignDeposit.geom).label("lon"),
    ST_Y(ForeignDeposit.geom).label("lat"),
)


def _to_out(row: Row[Any]) -> ForeignDepositOut:
    return ForeignDepositOut.model_validate(dict(row._mapping))


@router.get("", response_model=ForeignDepositPage, summary="List foreign deposits (paginated)")
def list_foreign(
    country: str | None = Query(None, description="Filter by country (case-insensitive)"),
    deposit_type: str | None = Query(None, description="Filter by deposit type"),
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
) -> ForeignDepositPage:
    filters = []
    if country:
        filters.append(ForeignDeposit.country.ilike(country))
    if deposit_type:
        filters.append(ForeignDeposit.deposit_type.ilike(deposit_type))

    total = db.scalar(
        select(func.count()).select_from(ForeignDeposit).where(*filters)
    ) or 0

    stmt = (
        select(*_COLUMNS)
        .where(*filters)
        .order_by(ForeignDeposit.id)
        .limit(page_size)
        .offset((page - 1) * page_size)
    )
    return ForeignDepositPage(
        total=total,
        page=page,
        page_size=page_size,
        items=[_to_out(row) for row in db.execute(stmt)],
    )
