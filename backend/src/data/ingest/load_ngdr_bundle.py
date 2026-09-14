"""Load every GeoJSON layer in the NGDR manganese bundle into ngdr_national.

Three of the five layers are polygon layers (exploration footprints and lease
boundaries); those are reduced to a representative interior point so they fit
the point geometry of ngdr_national. All original properties are kept verbatim
in raw_props.

Run with:  python -m src.data.ingest.load_ngdr_bundle
"""

from __future__ import annotations

import json
import tempfile
import zipfile
from pathlib import Path
from typing import Any

from shapely.geometry import shape
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.config.constants import classify_deposit_type
from src.config.settings import settings
from src.data.ingest import open_session, report, to_float, to_str, valid_lonlat, wkt_point
from src.db.models import NgdrNational

SOURCE_ZIP: Path = settings.DATA_RAW / "india" / "ngdr_manganese_bundle.zip"
CHUNK_SIZE: int = 500

#: Property names that may carry an explicit coordinate, in preference order.
_LON_KEYS: tuple[str, ...] = ("longitude", "long_", "exp_dd_longitude", "longitude_", "lon")
_LAT_KEYS: tuple[str, ...] = ("latitude", "lat", "exp_dd_latitude", "latitude_1")

_HOST_KEYS: tuple[str, ...] = ("host_rock", "hostrock", "geology", "formation")
_TYPE_KEYS: tuple[str, ...] = ("morphogen", "morphometr", "occurrence", "geology", "hostrock")
_STATE_KEYS: tuple[str, ...] = ("state_name", "state", "stname")
_COMMODITY_KEYS: tuple[str, ...] = ("commodity", "mineral_na", "comm_grp")


def _first(props: dict[str, Any], keys: tuple[str, ...]) -> str | None:
    """First non-empty string value among `keys`."""
    for key in keys:
        value = to_str(props.get(key))
        if value:
            return value
    return None


def _point_from_feature(feature: dict[str, Any]) -> tuple[float, float] | None:
    """Representative lon/lat for any geometry type, falling back to properties."""
    geometry = feature.get("geometry")
    if geometry:
        try:
            geom = shape(geometry)
            if not geom.is_empty:
                point = geom if geom.geom_type == "Point" else geom.representative_point()
                if valid_lonlat(point.x, point.y):
                    return point.x, point.y
        except Exception:  # noqa: BLE001 - fall through to the property coordinates
            pass

    props: dict[str, Any] = feature.get("properties") or {}
    lon = next((to_float(props.get(k)) for k in _LON_KEYS if props.get(k) is not None), None)
    lat = next((to_float(props.get(k)) for k in _LAT_KEYS if props.get(k) is not None), None)
    if valid_lonlat(lon, lat):
        return float(lon), float(lat)  # type: ignore[arg-type]
    return None


def _extract_bundle(zip_path: Path, dest: Path) -> list[Path]:
    """Unzip the bundle into `dest` and return its GeoJSON files, layer-sorted."""
    with zipfile.ZipFile(zip_path) as archive:
        archive.extractall(dest)
    return sorted(dest.rglob("*.geojson"))


def load_ngdr_bundle(
    zip_path: Path = SOURCE_ZIP,
    session: Session | None = None,
    chunk_size: int = CHUNK_SIZE,
) -> int:
    """Insert every point-reduced NGDR feature, tagged with its source layer."""
    db, owns = open_session(session)
    loaded = skipped = errors = 0
    try:
        existing_layers: set[str] = set(db.scalars(select(NgdrNational.source_layer)).all())

        with tempfile.TemporaryDirectory(prefix="ngdr_bundle_") as tmp:
            for geojson_path in _extract_bundle(zip_path, Path(tmp)):
                layer = geojson_path.stem
                if layer in existing_layers:
                    print(f"  layer {layer}: already loaded - skipped")
                    continue

                try:
                    payload = json.loads(geojson_path.read_text(encoding="utf-8"))
                except Exception as exc:  # noqa: BLE001
                    errors += 1
                    print(f"  layer {layer}: unreadable ({type(exc).__name__}: {exc})")
                    continue

                features: list[dict[str, Any]] = payload.get("features", [])
                print(f"  layer {layer}: {len(features)} features")

                pending: list[NgdrNational] = []
                for i, feature in enumerate(features):
                    try:
                        point = _point_from_feature(feature)
                        if point is None:
                            errors += 1
                            print(f"    {layer}[{i}]: no usable geometry - skipped")
                            continue
                        props = feature.get("properties") or {}
                        pending.append(
                            NgdrNational(
                                source_layer=layer,
                                geom=wkt_point(*point),
                                commodity=_first(props, _COMMODITY_KEYS) or "Manganese",
                                primary_type=classify_deposit_type(
                                    _first(props, _TYPE_KEYS)
                                ).value,
                                host_rock=_first(props, _HOST_KEYS),
                                state=_first(props, _STATE_KEYS),
                                raw_props=json.loads(json.dumps(props, default=str)),
                            )
                        )
                        loaded += 1
                        if len(pending) >= chunk_size:
                            db.add_all(pending)
                            db.commit()
                            pending.clear()
                    except Exception as exc:  # noqa: BLE001
                        errors += 1
                        print(f"    {layer}[{i}]: {type(exc).__name__}: {exc}")

                if pending:
                    db.add_all(pending)
                    db.commit()
                    pending.clear()
                existing_layers.add(layer)

        db.commit()
    finally:
        if owns:
            db.close()

    report(loaded, skipped, errors, str(zip_path))
    return loaded


if __name__ == "__main__":
    load_ngdr_bundle()
