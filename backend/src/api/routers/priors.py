"""Block grade prior endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.api.deps import get_db
from src.api.schemas import BlockPriorOut
from src.db.models import BlockGradePrior

router = APIRouter(prefix="/priors", tags=["priors"])

_COLUMNS = (
    BlockGradePrior.id,
    BlockGradePrior.block_name,
    BlockGradePrior.district,
    BlockGradePrior.state,
    BlockGradePrior.mn_pct_min,
    BlockGradePrior.mn_pct_max,
    BlockGradePrior.mn_pct_typ,
    BlockGradePrior.fe_pct_min,
    BlockGradePrior.fe_pct_max,
    BlockGradePrior.sio2_pct_min,
    BlockGradePrior.sio2_pct_max,
    BlockGradePrior.al2o3_pct_min,
    BlockGradePrior.al2o3_pct_max,
    BlockGradePrior.p_pct_min,
    BlockGradePrior.p_pct_max,
    BlockGradePrior.ore_class,
    BlockGradePrior.host_formation,
    BlockGradePrior.source,
    BlockGradePrior.notes,
    BlockGradePrior.prior_type,
    BlockGradePrior.n_samples,
)

@router.get("", response_model=list[BlockPriorOut], summary="List block grade priors")
def list_priors(
    district: str | None = Query(None, description="Filter by district (case-insensitive)"),
    db: Session = Depends(get_db),
) -> list[BlockPriorOut]:
    stmt = select(*_COLUMNS)
    if district:
        stmt = stmt.where(BlockGradePrior.district.ilike(district))
    rows = db.execute(stmt.order_by(BlockGradePrior.block_name)).all()
    return [BlockPriorOut.model_validate(dict(row._mapping)) for row in rows]


@router.get("/{block_name}", response_model=BlockPriorOut, summary="Get one block prior")
def get_prior(block_name: str, db: Session = Depends(get_db)) -> BlockPriorOut:
    row = db.execute(
        select(*_COLUMNS).where(BlockGradePrior.block_name.ilike(block_name))
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail=f"no prior for block '{block_name}'")
    return BlockPriorOut.model_validate(dict(row._mapping))
