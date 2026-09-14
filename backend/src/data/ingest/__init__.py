"""Ingest helpers shared by the Phase 1 loaders."""

from __future__ import annotations

import math
from datetime import date, datetime
from typing import Any

from sqlalchemy.orm import Session

from src.db.session import SessionLocal


def to_float(value: Any) -> float | None:
    """Coerce a CSV cell to float, mapping blanks/NaN/sentinels to None."""
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    text = str(value).strip()
    if text == "" or text.lower() in {"nan", "na", "n/a", "none", "null", "-"}:
        return None
    try:
        parsed = float(text)
    except ValueError:
        return None
    return None if math.isnan(parsed) else parsed


def to_int(value: Any) -> int | None:
    parsed = to_float(value)
    return None if parsed is None else int(parsed)


def to_str(value: Any, default: str | None = None) -> str | None:
    """Coerce a CSV cell to a stripped string, mapping blanks/NaN to `default`."""
    if value is None:
        return default
    if isinstance(value, float) and math.isnan(value):
        return default
    text = str(value).strip()
    if text == "" or text.lower() in {"nan", "none", "null"}:
        return default
    return text


def to_date(value: Any) -> date | None:
    """Parse an ISO-ish date cell; returns None on anything unparseable."""
    text = to_str(value)
    if text is None:
        return None
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(text[:10], fmt).date()
        except ValueError:
            continue
    return None


def valid_lonlat(lon: float | None, lat: float | None) -> bool:
    """True only for finite coordinates inside the WGS84 domain and not at null island."""
    if lon is None or lat is None:
        return False
    if not (-180.0 <= lon <= 180.0 and -90.0 <= lat <= 90.0):
        return False
    return not (lon == 0.0 and lat == 0.0)


def wkt_point(lon: float, lat: float) -> str:
    """EWKT point literal that GeoAlchemy2 accepts directly."""
    return f"SRID=4326;POINT({lon} {lat})"


def open_session(session: Session | None = None) -> tuple[Session, bool]:
    """Return (session, owns_session). Loaders accept an injected session for tests."""
    if session is not None:
        return session, False
    return SessionLocal(), True


def report(loaded: int, skipped: int, errors: int, source: str) -> None:
    """Uniform completion line for every loader."""
    print(f"Loaded {loaded} rows from {source}")
    print(f"  skipped (already present): {skipped}   errors: {errors}")
