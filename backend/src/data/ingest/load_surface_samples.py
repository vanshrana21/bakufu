"""Load Katori-Jhiriya surface XRF samples into the surface_samples table.

Run with:  python -m src.data.ingest.load_surface_samples
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.config.settings import settings
from src.data.ingest import open_session, report, to_float, to_str, valid_lonlat, wkt_point
from src.db.models import SurfaceSample

SOURCE_CSV: Path = settings.DATA_RAW / "india" / "katori_surface_samples.csv"

_ASSAY_COLUMNS: tuple[str, ...] = (
    "mn_pct",
    "fe_pct",
    "si_pct",
    "sio2_pct",
    "al_pct",
    "al2o3_pct",
    "ca_pct",
    "p_pct",
)


def load_surface_samples(csv_path: Path = SOURCE_CSV, session: Session | None = None) -> int:
    """Insert surface samples, skipping sample_ids already stored."""
    db, owns = open_session(session)
    loaded = skipped = errors = 0
    try:
        df = pd.read_csv(csv_path)
        existing: set[str] = set(db.scalars(select(SurfaceSample.sample_id)).all())

        for idx, row in df.iterrows():
            try:
                sample_id = to_str(row.get("sample_id"))
                if not sample_id:
                    print(f"  row {idx}: missing sample_id - skipped")
                    errors += 1
                    continue
                if sample_id in existing:
                    skipped += 1
                    continue

                lon = to_float(row.get("longitude_dd", row.get("lon")))
                lat = to_float(row.get("latitude_dd", row.get("lat")))
                if not valid_lonlat(lon, lat):
                    print(f"  row {idx} ({sample_id}): invalid lon/lat {lon},{lat} - skipped")
                    errors += 1
                    continue

                assays = {col: to_float(row.get(col)) for col in _ASSAY_COLUMNS}
                db.add(
                    SurfaceSample(
                        sample_id=sample_id,
                        sample_type=to_str(row.get("sample_type"), "surface_xrf"),
                        block_name=to_str(row.get("block_name")),
                        district=to_str(row.get("district")),
                        state=to_str(row.get("state")),
                        geom=wkt_point(lon, lat),
                        notes=to_str(row.get("notes")),
                        source=to_str(row.get("source")),
                        **assays,
                    )
                )
                existing.add(sample_id)
                loaded += 1
            except Exception as exc:  # noqa: BLE001
                errors += 1
                print(f"  row {idx}: {type(exc).__name__}: {exc}")

        db.commit()
    finally:
        if owns:
            db.close()

    report(loaded, skipped, errors, str(csv_path))
    return loaded


if __name__ == "__main__":
    load_surface_samples()
