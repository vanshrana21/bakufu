"""Assemble the Phase 1 training table: boreholes + block priors + raster features.

Run with:  python -m src.data.preprocess.build_training_set
"""

from __future__ import annotations

import argparse

from pathlib import Path

import pandas as pd
from geoalchemy2.functions import ST_X, ST_Y
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.config.settings import settings
from src.data.ingest import open_session
from src.data.preprocess.compute_indices import INDEX_COLUMNS, add_indices
from src.data.preprocess.extract_features import FEATURE_COLUMNS, extract_features_bulk
from src.db.models import BlockGradePrior, Borehole

OUTPUT_PATH: Path = settings.DATA_PROCESSED / "training_set_v1.parquet"

#: Prior columns carried through as labels / label bounds.
LABEL_COLUMNS: list[str] = [
    "mn_pct_min",
    "mn_pct_max",
    "mn_pct_typ",
    "fe_pct_min",
    "fe_pct_max",
    "ore_class",
    "host_formation",
    "prior_type",
]


def _read_boreholes(db: Session) -> pd.DataFrame:
    """Boreholes with geometry decomposed into lon/lat columns."""
    stmt = select(
        Borehole.id.label("borehole_id"),
        Borehole.nuid,
        Borehole.borehole_no,
        Borehole.block_name,
        Borehole.district,
        Borehole.state,
        Borehole.length_m,
        Borehole.rl_collar_m,
        ST_X(Borehole.geom).label("lon"),
        ST_Y(Borehole.geom).label("lat"),
    ).order_by(Borehole.id)
    return pd.DataFrame(db.execute(stmt).mappings().all())


def _read_priors(db: Session) -> pd.DataFrame:
    stmt = select(
        BlockGradePrior.block_name,
        *[getattr(BlockGradePrior, column) for column in LABEL_COLUMNS],
    )
    return pd.DataFrame(db.execute(stmt).mappings().all())


def build_training_set(
    output_path: Path = OUTPUT_PATH,
    s2_path: Path | None = None,
    dem_path: Path | None = None,
    session: Session | None = None,
) -> pd.DataFrame:
    """Build and persist the v1 training table, returning it as a DataFrame."""
    db, owns = open_session(session)
    try:
        boreholes = _read_boreholes(db)
        priors = _read_priors(db)
    finally:
        if owns:
            db.close()

    if boreholes.empty:
        raise RuntimeError("no boreholes in the database - run scripts/load_all.py first")

    # Left join keeps every borehole even where its block has no published prior.
    merged = boreholes.merge(priors, on="block_name", how="left")

    featured = extract_features_bulk(merged, s2_path=s2_path, dem_path=dem_path)
    result = add_indices(featured)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    result.to_parquet(output_path, index=False)

    labelled = int(result["mn_pct_typ"].notna().sum()) if "mn_pct_typ" in result else 0
    feature_columns = [c for c in FEATURE_COLUMNS + INDEX_COLUMNS if c in result.columns]

    print("=" * 60)
    print("TRAINING SET v1")
    print("=" * 60)
    print(f"  path      : {output_path}")
    print(f"  rows      : {len(result)}")
    print(f"  columns   : {len(result.columns)}")
    print(f"  features  : {len(feature_columns)} -> {feature_columns}")
    print(f"  labels    : {labelled} rows with mn_pct_typ")
    print(f"  no-prior  : {len(result) - labelled} rows without a block prior")
    print(f"  all cols  : {list(result.columns)}")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--s2-path", default=None, help="Sentinel-2 mosaic to sample (default: smoke test)")
    parser.add_argument("--dem-path", default=None, help="DEM raster to sample (default: smoke test)")
    parser.add_argument("--output", default=None, help="Output parquet path")
    args = parser.parse_args()
    build_training_set(
        s2_path=Path(args.s2_path) if args.s2_path else None,
        dem_path=Path(args.dem_path) if args.dem_path else None,
        output_path=Path(args.output) if args.output else OUTPUT_PATH,
    )


if __name__ == "__main__":
    main()
