"""Block grade prior endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.api.deps import get_db
from src.api.schemas import BlockPriorOut
from src.db.models import BlockGradePrior

router = APIRouter(prefix="/priors", tags=["priors"])


@router.get("", response_model=list[BlockPriorOut], summary="List block grade priors")
def list_priors(
    district: str | None = Query(None, description="Filter by district (case-insensitive)"),
    db: Session = Depends(get_db),
) -> list[BlockPriorOut]:
    stmt = select(BlockGradePrior)
    if district:
        stmt = stmt.where(BlockGradePrior.district.ilike(district))
    rows = db.scalars(stmt.order_by(BlockGradePrior.block_name)).all()
    return [BlockPriorOut.model_validate(row) for row in rows]


@router.get("/{block_name}", response_model=BlockPriorOut, summary="Get one block prior")
def get_prior(block_name: str, db: Session = Depends(get_db)) -> BlockPriorOut:
    row = db.scalars(
        select(BlockGradePrior).where(BlockGradePrior.block_name.ilike(block_name))
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail=f"no prior for block '{block_name}'")
    return BlockPriorOut.model_validate(row)
