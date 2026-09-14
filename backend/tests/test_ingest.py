"""Row-count and geometry integrity checks for the loaded tables."""

from __future__ import annotations

import pytest
from geoalchemy2.functions import ST_GeometryType, ST_IsValid
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from tests.conftest import requires_db

from src.db.models import BlockGradePrior, Borehole, ForeignDeposit

pytestmark = requires_db


def _count(db: Session, model: type) -> int:
    return db.scalar(select(func.count()).select_from(model)) or 0


def test_load_boreholes_count(db_session: Session) -> None:
    assert _count(db_session, Borehole) == 46


def test_load_priors_count(db_session: Session) -> None:
    assert _count(db_session, BlockGradePrior) == 7


def test_load_foreign_count(db_session: Session) -> None:
    assert _count(db_session, ForeignDeposit) > 1000


def test_no_null_geoms(db_session: Session) -> None:
    """Every borehole must carry a valid POINT geometry."""
    rows = db_session.execute(
        select(
            Borehole.id,
            ST_GeometryType(Borehole.geom).label("geom_type"),
            ST_IsValid(Borehole.geom).label("is_valid"),
        )
    ).all()

    assert rows, "no boreholes loaded"
    bad = [
        row.id for row in rows if row.geom_type != "ST_Point" or not row.is_valid
    ]
    assert not bad, f"boreholes with missing/invalid geometry: {bad}"


def test_priors_have_prior_type(db_session: Session) -> None:
    """prior_type is inferred at load time and must never be null."""
    missing = db_session.scalars(
        select(BlockGradePrior.block_name).where(BlockGradePrior.prior_type.is_(None))
    ).all()
    assert not missing, f"priors missing prior_type: {missing}"
