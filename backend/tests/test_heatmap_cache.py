"""The bounded heatmap caches in src/api/routers/reference.py.

Both the payload cache and the per-key computation locks used to be plain
dicts that only ever grew: every distinct bbox a client asked for left a
payload and a lock behind for the life of the process. They are now bounded
caches, and these tests pin the bound, the expiry and the single-flight
behaviour that keeps one cold grid from being scored twice at once.
"""

from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Any

import pytest
from cachetools import TTLCache

from src.api.routers import reference

BBOX = (79.0, 21.3, 80.6, 22.1)


@pytest.fixture(autouse=True)
def _clean_memory() -> None:
    reference.clear_heatmap_memory()


def _payload(grid_size: int = 4) -> dict[str, Any]:
    return {
        "bbox": list(BBOX),
        "grid": {
            "n_cols": grid_size, "n_rows": grid_size,
            "cell_width_deg": 0.4, "cell_height_deg": 0.2, "origin": "top_left",
        },
        "scores": [[0.5] * grid_size for _ in range(grid_size)],
        "cells": {
            "cells_total": grid_size**2, "cells_outside_raster": 0,
            "cells_masked_out": 0, "cells_scored": grid_size**2,
        },
    }


# --- the caches the module actually uses --------------------------------


def test_both_caches_are_bounded() -> None:
    assert isinstance(reference._MEMORY, TTLCache)
    assert reference._MEMORY.maxsize == reference.MEMORY_MAX_ENTRIES
    assert reference._MEMORY.ttl == reference.MEMORY_TTL_SECONDS
    assert isinstance(reference._KEY_LOCKS, TTLCache)
    assert reference._KEY_LOCKS.maxsize == reference.KEY_LOCK_MAX_ENTRIES
    assert reference._KEY_LOCKS.ttl == reference.KEY_LOCK_TTL_SECONDS


def test_payloads_are_evicted_by_size_and_by_age(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(reference, "_MEMORY", TTLCache(maxsize=2, ttl=0.05, timer=time.monotonic))
    for key in ("a", "b", "c"):
        reference._memory_write(key, {"key": key})

    assert len(reference._MEMORY) == 2
    assert reference._memory_read("a") is None  # least recently used, dropped
    assert reference._memory_read("c") == {"key": "c"}

    time.sleep(0.06)
    assert reference._memory_read("c") is None
    assert len(reference._MEMORY) == 0


def test_a_key_keeps_one_lock_and_the_table_stays_bounded(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(reference, "_KEY_LOCKS", TTLCache(maxsize=4, ttl=60, timer=time.monotonic))
    assert reference._key_lock("same") is reference._key_lock("same")
    assert reference._key_lock("same") is not reference._key_lock("other")

    for index in range(50):
        reference._key_lock(f"key-{index}")
    assert len(reference._KEY_LOCKS) == 4


def test_a_lock_in_use_does_not_expire(monkeypatch: pytest.MonkeyPatch) -> None:
    """Re-inserting on every lookup restarts the TTL, so a busy key keeps its lock."""
    monkeypatch.setattr(reference, "_KEY_LOCKS", TTLCache(maxsize=8, ttl=0.08, timer=time.monotonic))
    first = reference._key_lock("busy")
    for _ in range(4):
        time.sleep(0.03)
        assert reference._key_lock("busy") is first


# --- single flight -------------------------------------------------------


def test_one_cold_computation_per_key_under_concurrency(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from src.models.prospectivity import predict

    monkeypatch.setattr(reference, "CACHE_DIR", tmp_path / "cache")
    calls: list[float] = []

    def slow_grid(*_args: Any, grid_size: int = 4, **_kwargs: Any) -> dict[str, Any]:
        calls.append(time.monotonic())
        time.sleep(0.2)  # a real cold grid is ~38s
        return _payload(grid_size)

    monkeypatch.setattr(predict, "heatmap_grid", slow_grid)

    results: list[dict[str, Any]] = []
    barrier = threading.Barrier(8)

    def ask() -> None:
        barrier.wait()
        results.append(reference.compute_heatmap(*BBOX, grid_size=4, mask="none"))

    threads = [threading.Thread(target=ask) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert len(calls) == 1, "a second thread started its own pass over the raster"
    assert len(results) == 8
    assert sum(1 for result in results if result["cached"]) == 7
    assert all(result["scores"] == _payload(4)["scores"] for result in results)
    # One disk tile, not eight.
    assert len(list((tmp_path / "cache").glob("heatmap_*.json"))) == 1
