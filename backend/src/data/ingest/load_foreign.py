"""Load the foreign (non-India) manganese deposit compilation.

Inserts in chunks because the Supabase connection is over the internet.

Run with:  python -m src.data.ingest.load_foreign
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from geoalchemy2.functions import ST_X, ST_Y
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.config.constants import classify_deposit_type
from src.config.settings import settings
from src.data.ingest import open_session, report, to_float, to_str, valid_lonlat, wkt_point
from src.db.models import ForeignDeposit

SOURCE_CSV: Path = settings.DATA_RAW / "foreign" / "foreign_manganese_deposits_20260826.csv"
CHUNK_SIZE: int = 500

#: Coordinate precision (decimal places) used in the identity key. The source
#: carries many distinct occurrences sharing a name - 73 Australian deposits
#: are all called "Unnamed" - so location is part of what makes a row unique.
_COORD_PRECISION: int = 5

DedupKey = tuple[str, str | None, float, float]


def _identity(name: str, country: str | None, lon: float, lat: float) -> DedupKey:
    return name, country, round(lon, _COORD_PRECISION), round(lat, _COORD_PRECISION)


def load_foreign(
    csv_path: Path = SOURCE_CSV,
    session: Session | None = None,
    chunk_size: int = CHUNK_SIZE,
) -> int:
    """Insert foreign deposits in chunks, skipping rows already stored.

    Identity is (deposit_name, country, lon, lat) - see `_identity`.
    """
    db, owns = open_session(session)
    loaded = skipped = errors = 0
    try:
        df = pd.read_csv(csv_path)
        existing: set[DedupKey] = {
            _identity(name, country, float(lon), float(lat))
            for name, country, lon, lat in db.execute(
                select(
                    ForeignDeposit.deposit_name,
                    ForeignDeposit.country,
                    ST_X(ForeignDeposit.geom),
                    ST_Y(ForeignDeposit.geom),
                )
            )
        }

        pending: list[ForeignDeposit] = []
        for idx, row in df.iterrows():
            try:
                name = to_str(row.get("deposit_name"))
                country = to_str(row.get("country"))
                if not name:
                    print(f"  row {idx}: missing deposit_name - skipped")
                    errors += 1
                    continue
                lon = to_float(row.get("longitude"))
                lat = to_float(row.get("latitude"))
                if not valid_lonlat(lon, lat):
                    print(f"  row {idx} ({name}): invalid lon/lat {lon},{lat} - skipped")
                    errors += 1
                    continue

                key = _identity(name, country, float(lon), float(lat))
                if key in existing:
                    skipped += 1
                    continue

                raw_type = to_str(row.get("deposit_type")) or to_str(row.get("deposit_type_raw"))
                pending.append(
                    ForeignDeposit(
                        deposit_name=name,
                        country=country,
                        deposit_type=classify_deposit_type(raw_type).value,
                        host_rock=to_str(row.get("host_rock")),
                        age=to_str(row.get("age")),
                        grade_pct=to_float(row.get("grade_pct")),
                        tonnage=to_float(row.get("tonnage")),
                        geom=wkt_point(lon, lat),
                        source=to_str(row.get("source")),
                        reference=to_str(row.get("reference")),
                    )
                )
                existing.add(key)
                loaded += 1

                if len(pending) >= chunk_size:
                    db.add_all(pending)
                    db.commit()
                    print(f"  committed chunk of {len(pending)} (running total {loaded})")
                    pending.clear()
            except Exception as exc:  # noqa: BLE001
                errors += 1
                print(f"  row {idx}: {type(exc).__name__}: {exc}")

        if pending:
            db.add_all(pending)
            db.commit()
            print(f"  committed final chunk of {len(pending)} (running total {loaded})")
    finally:
        if owns:
            db.close()

    report(loaded, skipped, errors, str(csv_path))
    return loaded


if __name__ == "__main__":
    load_foreign()
