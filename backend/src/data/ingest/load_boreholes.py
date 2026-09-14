"""Load NGDR borehole collars into the boreholes table.

Run with:  python -m src.data.ingest.load_boreholes
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.config.settings import settings
from src.data.ingest import (
    open_session,
    report,
    to_date,
    to_float,
    to_str,
    valid_lonlat,
    wkt_point,
)
from src.db.models import Borehole

SOURCE_CSV: Path = settings.DATA_RAW / "india" / "mn_boreholes_collars.csv"


def load_boreholes(csv_path: Path = SOURCE_CSV, session: Session | None = None) -> int:
    """Insert borehole collars, skipping any (nuid, borehole_no) already stored."""
    db, owns = open_session(session)
    loaded = skipped = errors = 0
    try:
        df = pd.read_csv(csv_path)
        existing: set[tuple[str, str]] = {
            (nuid, no) for nuid, no in db.execute(select(Borehole.nuid, Borehole.borehole_no))
        }

        for idx, row in df.iterrows():
            try:
                nuid = to_str(row.get("nuid"))
                borehole_no = to_str(row.get("borehole_no"))
                if not nuid or not borehole_no:
                    print(f"  row {idx}: missing nuid/borehole_no - skipped")
                    errors += 1
                    continue
                if (nuid, borehole_no) in existing:
                    skipped += 1
                    continue

                lon = to_float(row.get("lon", row.get("longitude_dd")))
                lat = to_float(row.get("lat", row.get("latitude_dd")))
                if not valid_lonlat(lon, lat):
                    print(f"  row {idx} ({borehole_no}): invalid lon/lat {lon},{lat} - skipped")
                    errors += 1
                    continue

                db.add(
                    Borehole(
                        nuid=nuid,
                        borehole_no=borehole_no,
                        block_name=to_str(row.get("block_name"), "UNKNOWN"),
                        district=to_str(row.get("district"), "UNKNOWN"),
                        state=to_str(row.get("state"), "UNKNOWN"),
                        geom=wkt_point(lon, lat),
                        length_m=to_float(row.get("length_m")),
                        rl_collar_m=to_float(row.get("rl_collar_m")),
                        rl_bottom_m=to_float(row.get("rl_bottom_m")),
                        borehole_type=to_str(row.get("borehole_type", row.get("type"))),
                        start_date=to_date(row.get("start_date")),
                        end_date=to_date(row.get("end_date")),
                        commodity=to_str(row.get("commodity"), "Manganese"),
                        source="NGDR",
                    )
                )
                existing.add((nuid, borehole_no))
                loaded += 1
            except Exception as exc:  # noqa: BLE001 - one bad row must not kill the batch
                errors += 1
                print(f"  row {idx}: {type(exc).__name__}: {exc}")

        db.commit()
    finally:
        if owns:
            db.close()

    report(loaded, skipped, errors, str(csv_path))
    return loaded


if __name__ == "__main__":
    load_boreholes()
