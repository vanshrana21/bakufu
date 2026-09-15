"""Phase 4 reference endpoints: mines and the prospectivity heatmap."""

from __future__ import annotations

import copy
import hashlib
import json
import logging
import threading
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request

from src.api.errors import ModelNotLoaded
from src.config.settings import settings

from src.reference.moil_mines import (
    GENERIC_FLEETS,
    MOIL_MINES,
    OPENCAST_FLEET_VOCAB,
    SOURCE_URLS,
    UNDERGROUND_FLEET_VOCAB,
)

logger = logging.getLogger("api.reference")

router = APIRouter(tags=["reference"])

VALID_STATES = ("MH", "MP")
VALID_MINE_TYPES = ("underground", "opencast", "mixed")


def _sources(tags: list[str]) -> list[dict[str, str]]:
    return [{"tag": tag, "url": SOURCE_URLS[tag]} for tag in tags if tag in SOURCE_URLS]


def _mine_payload(name: str, mine: dict[str, object]) -> dict[str, object]:
    return {
        "mine_name": name,
        "state": mine["state"],
        "district": mine["district"],
        "mine_type": mine["mine_type"],
        "equipment": list(mine["equipment"]),
        "capacity_target_tonnes": mine["capacity_target_tonnes"],
        "notes": mine["notes"],
        "sources": _sources(list(mine["sources"])),
        # Present on Kandri alone, so it is always emitted - as null elsewhere -
        # rather than making the frontend probe for an optional key.
        "type_note": mine.get("type_note"),
    }


@router.get("/mines", summary="List MOIL operating mines")
def list_mines(
    request: Request,
    state: str | None = Query(None, description=f"Filter by state. One of {VALID_STATES}."),
    mine_type: str | None = Query(None, description=f"Filter by type. One of {VALID_MINE_TYPES}."),
) -> dict[str, object]:
    if state is not None and state not in VALID_STATES:
        raise HTTPException(
            status_code=422,
            detail=f"state must be one of {', '.join(VALID_STATES)}",
        )
    if mine_type is not None and mine_type not in VALID_MINE_TYPES:
        raise HTTPException(
            status_code=422,
            detail=f"mine_type must be one of {', '.join(VALID_MINE_TYPES)}",
        )

    selected = {
        name: mine
        for name, mine in MOIL_MINES.items()
        if (state is None or mine["state"] == state)
        and (mine_type is None or mine["mine_type"] == mine_type)
    }

    generic = sum(1 for m in selected.values() if set(m["equipment"]) & set(GENERIC_FLEETS))
    return {
        "mines": [_mine_payload(n, m) for n, m in selected.items()],
        "counts": {
            "total": len(selected),
            "underground": sum(1 for m in selected.values() if m["mine_type"] == "underground"),
            "opencast": sum(1 for m in selected.values() if m["mine_type"] == "opencast"),
            "mixed": sum(1 for m in selected.values() if m["mine_type"] == "mixed"),
            "MH": sum(1 for m in selected.values() if m["state"] == "MH"),
            "MP": sum(1 for m in selected.values() if m["state"] == "MP"),
            "with_capacity_target": sum(
                1 for m in selected.values() if m["capacity_target_tonnes"] is not None
            ),
            "with_generic_fleet_only": generic,
        },
    }


@router.get("/mines/{mine_name}", summary="One mine in detail")
def get_mine(mine_name: str) -> dict[str, object]:
    mine = MOIL_MINES.get(mine_name)
    if mine is None:
        raise HTTPException(
            status_code=404,
            detail=f"mine {mine_name!r} not found. Known mines: {', '.join(sorted(MOIL_MINES))}",
        )

    payload = _mine_payload(mine_name, mine)
    is_generic = bool(set(mine["equipment"]) & set(GENERIC_FLEETS))
    vocabulary = (
        OPENCAST_FLEET_VOCAB if mine["mine_type"] == "opencast" else UNDERGROUND_FLEET_VOCAB
    )
    payload["fleet_vocabulary"] = {
        "applicable": list(vocabulary),
        "is_generic_fallback": is_generic,
    }
    return payload


# --- prospectivity heatmap ---------------------------------------------

CACHE_DIR = settings.DATA_PROCESSED.parent / "cache"
CACHE_TTL_SECONDS = 24 * 3600
#: In-memory tier in front of the disk cache. It holds only payloads the model
#: actually computed; the startup warmer refreshes it on this interval.
MEMORY_TTL_SECONDS = 10 * 60
MIN_GRID, MAX_GRID = 8, 128

_MEMORY: dict[str, tuple[float, dict[str, Any]]] = {}
_KEY_LOCKS: dict[str, threading.Lock] = {}
_KEY_LOCKS_GUARD = threading.Lock()


def clear_heatmap_memory() -> None:
    _MEMORY.clear()


def _memory_read(key: str) -> dict[str, Any] | None:
    entry = _MEMORY.get(key)
    if entry is None:
        return None
    stored_at, payload = entry
    if time.monotonic() - stored_at > MEMORY_TTL_SECONDS:
        _MEMORY.pop(key, None)
        return None
    return payload


def _memory_write(key: str, payload: dict[str, Any]) -> None:
    _MEMORY[key] = (time.monotonic(), payload)


def _key_lock(key: str) -> threading.Lock:
    with _KEY_LOCKS_GUARD:
        return _KEY_LOCKS.setdefault(key, threading.Lock())


def _cache_key(bbox: tuple[float, ...], grid_size: int, mask: str, version: str) -> str:
    """Model version is in the key so a promotion cannot serve stale tiles."""
    raw = f"{[round(v, 4) for v in bbox]}|{grid_size}|{mask}|{version}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _cache_read(key: str) -> dict[str, Any] | None:
    path = CACHE_DIR / f"heatmap_{key}.json"
    if not path.exists():
        return None
    if time.time() - path.stat().st_mtime > CACHE_TTL_SECONDS:
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 - a corrupt tile just misses the cache
        return None


def _cache_write(key: str, payload: dict[str, Any]) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    try:
        (CACHE_DIR / f"heatmap_{key}.json").write_text(
            json.dumps(payload), encoding="utf-8"
        )
    except Exception:  # noqa: BLE001 - caching is an optimisation, never fatal
        logger.warning("could not write heatmap cache %s", key)


def compute_heatmap(
    min_lon: float, min_lat: float, max_lon: float, max_lat: float,
    grid_size: int, mask: str,
) -> dict[str, Any]:
    """Score a grid and apply the mask: memory, then disk, then the model.

    A masked surface is derived from the unmasked grid for the same bbox, so
    the four mask variants cost one model pass rather than four.
    """
    from src.data.masks.registry import apply_mask
    from src.models.prospectivity.predict import ACTIVE_MODEL_PATH, heatmap_grid

    version = Path(ACTIVE_MODEL_PATH).stem
    key = _cache_key((min_lon, min_lat, max_lon, max_lat), grid_size, mask, version)
    hit = _memory_read(key)
    if hit is not None:
        return {**hit, "cached": True}

    # One computation per key: a request that arrives while the warmer is
    # scoring the same surface waits for that result instead of starting a
    # second pass over the raster.
    with _key_lock(key):
        hit = _memory_read(key)
        if hit is not None:
            return {**hit, "cached": True}
        cached = _cache_read(key)
        if cached is not None:
            _memory_write(key, cached)
            return {**cached, "cached": True}

        if mask == "none":
            payload = heatmap_grid(min_lon, min_lat, max_lon, max_lat, grid_size=grid_size)
            payload["generated_at"] = datetime.now(UTC).isoformat(timespec="seconds")
        else:
            base = compute_heatmap(min_lon, min_lat, max_lon, max_lat, grid_size, "none")
            # Deep copy: the base payload is shared with the cache. Its
            # generated_at is kept because that is when the model scored.
            payload = copy.deepcopy({k: v for k, v in base.items() if k != "cached"})
            _apply_mask(payload, min_lon, max_lat, mask, apply_mask)

        payload["mask_applied"] = mask
        _cache_write(key, payload)
        _memory_write(key, payload)
        return {**payload, "cached": False}


def _apply_mask(
    payload: dict[str, Any], min_lon: float, max_lat: float, mask: str,
    apply_mask: Callable[[float, float, float, str], tuple[float, str]],
) -> None:
    """Post-filter an unmasked lattice in place."""
    cell_w = payload["grid"]["cell_width_deg"]
    cell_h = payload["grid"]["cell_height_deg"]
    masked_out = 0
    for row_index, row in enumerate(payload["scores"]):
        lat = max_lat - (row_index + 0.5) * cell_h
        for col_index, value in enumerate(row):
            if value is None:
                continue  # no data stays no data; a mask cannot fill it in
            lon = min_lon + (col_index + 0.5) * cell_w
            kept, _decision = apply_mask(lat, lon, value, mask)
            row[col_index] = float(min(max(kept, 0.0), 0.99))
            masked_out += int(kept <= 0.0 < value)
    payload["cells"]["cells_masked_out"] = masked_out


@router.get("/prospectivity/heatmap", summary="Gridded prospectivity for the map view")
def get_heatmap(
    min_lon: float = Query(..., ge=-180.0, le=180.0),
    min_lat: float = Query(..., ge=-90.0, le=90.0),
    max_lon: float = Query(..., ge=-180.0, le=180.0),
    max_lat: float = Query(..., ge=-90.0, le=90.0),
    grid_size: int = Query(32, description=f"Cells per side, {MIN_GRID}-{MAX_GRID}."),
    mask: str = Query("none", description="Geological post-filter."),
) -> dict[str, Any]:
    """A lattice aligned to the bbox, unlike /predict/bbox.

    See docs/known_issues.md #1: that endpoint reprojects per point, so its
    cells do not share row latitudes and some fall outside the requested bbox.
    """
    from src.data.masks.registry import VALID_MASKS

    if min_lon >= max_lon or min_lat >= max_lat:
        raise HTTPException(
            status_code=422,
            detail="min_lon/min_lat must be less than max_lon/max_lat",
        )
    if not MIN_GRID <= grid_size <= MAX_GRID:
        raise HTTPException(
            status_code=422,
            detail=f"grid_size must be between {MIN_GRID} and {MAX_GRID}, got {grid_size}",
        )
    if mask not in VALID_MASKS:
        raise HTTPException(
            status_code=422,
            detail=f"unknown mask {mask!r}; expected one of {', '.join(VALID_MASKS)}",
        )

    try:
        return compute_heatmap(min_lon, min_lat, max_lon, max_lat, grid_size, mask)
    except FileNotFoundError as exc:
        raise ModelNotLoaded("prospectivity model or raster", str(exc)) from exc
