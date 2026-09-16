"""The bounded heatmap caches and scoring guards in src/api/routers/reference.py.

The payload cache used to be a plain dict that only grew: every distinct bbox a
client asked for left a payload behind for the life of the process. It is a
bounded TTL cache now. The per-key computation locks are bounded differently -
by reference counting - because evicting a lock somebody still holds destroys
the mutual exclusion it exists for, and a ceiling on concurrent scoring keeps a
flood of distinct viewports from running one model pass per request.
"""

from __future__ import annotations

import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest
from cachetools import TTLCache

from src.api.errors import ServiceBusy
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


# --- the payload cache ---------------------------------------------------


def test_the_payload_cache_is_bounded() -> None:
    assert isinstance(reference._MEMORY, TTLCache)
    assert reference._MEMORY.maxsize == reference.MEMORY_MAX_ENTRIES
    assert reference._MEMORY.ttl == reference.MEMORY_TTL_SECONDS


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


# --- the per-key locks ---------------------------------------------------


def test_the_lock_table_empties_itself() -> None:
    # Relative to whatever the startup warmer may be holding on its own thread:
    # what matters is that this test's keys are gone afterwards.
    baseline = set(reference._KEY_LOCKS)
    with reference._key_guard("one"):
        assert set(reference._KEY_LOCKS) - baseline == {"one"}
        with reference._key_guard("two"):
            assert set(reference._KEY_LOCKS) - baseline == {"one", "two"}
    assert set(reference._KEY_LOCKS) - baseline == set()


def test_a_lock_in_use_is_never_replaced() -> None:
    """The bug an LRU or TTL lock table would reintroduce: two locks, one key."""
    held = reference._KEY_LOCKS
    entered = threading.Event()
    release = threading.Event()
    second_entered = threading.Event()

    def hold() -> None:
        with reference._key_guard("busy"):
            entered.set()
            release.wait(5)

    def follow() -> None:
        with reference._key_guard("busy"):
            second_entered.set()

    holder = threading.Thread(target=hold)
    holder.start()
    assert entered.wait(5)
    mine = held["busy"]

    follower = threading.Thread(target=follow)
    follower.start()
    # Thousands of other keys come and go while "busy" is held.
    for index in range(5_000):
        with reference._key_guard(f"key-{index}"):
            pass

    assert held["busy"] is mine, "the held lock was replaced"
    assert not second_entered.is_set(), "a second thread entered while the key was held"
    release.set()
    holder.join(5)
    follower.join(5)
    assert second_entered.is_set()
    assert "busy" not in reference._KEY_LOCKS


def test_the_lock_table_is_bounded_by_work_in_flight() -> None:
    baseline = len(reference._KEY_LOCKS)
    for index in range(2_000):
        with reference._key_guard(f"key-{index}"):
            assert len(reference._KEY_LOCKS) <= baseline + 1
    assert len(reference._KEY_LOCKS) <= baseline


# --- concurrent scoring --------------------------------------------------


def test_scoring_slots_are_limited_and_released(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(reference, "_SCORING_SLOTS", threading.BoundedSemaphore(1))
    monkeypatch.setattr(reference, "SCORING_QUEUE_TIMEOUT_SECONDS", 0.05)

    with reference._scoring_slot():
        with pytest.raises(ServiceBusy) as refused:
            with reference._scoring_slot():
                pass
    assert refused.value.status_code == 503
    assert refused.value.error_code == "service_busy"

    # The slot is handed back, so the next caller is served.
    with reference._scoring_slot():
        pass


def test_a_flood_of_distinct_viewports_cannot_pile_up(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Each distinct bbox is its own key, so only the slot ceiling holds them back."""
    from src.models.prospectivity import predict

    monkeypatch.setattr(reference, "CACHE_DIR", tmp_path / "cache")
    monkeypatch.setattr(reference, "_SCORING_SLOTS", threading.BoundedSemaphore(2))
    monkeypatch.setattr(reference, "SCORING_QUEUE_TIMEOUT_SECONDS", 5)
    live = 0
    peak = 0
    counter = threading.Lock()

    def slow_grid(*_args: Any, grid_size: int = 4, **_kwargs: Any) -> dict[str, Any]:
        nonlocal live, peak
        with counter:
            live += 1
            peak = max(peak, live)
        time.sleep(0.15)
        with counter:
            live -= 1
        return _payload(grid_size)

    monkeypatch.setattr(predict, "heatmap_grid", slow_grid)

    def ask(index: int) -> None:
        reference.compute_heatmap(79.0 + index / 100, 21.3, 80.6, 22.1, grid_size=4, mask="none")

    threads = [threading.Thread(target=ask, args=(index,)) for index in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert peak <= 2, f"{peak} model passes ran at once"


# --- the disk tier -------------------------------------------------------


def test_the_disk_cache_stays_inside_its_budget(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Mandatory 11: thousands of unique viewports must not fill the disk."""
    monkeypatch.setattr(reference, "CACHE_DIR", tmp_path / "cache")
    monkeypatch.setattr(reference, "CACHE_MAX_FILES", 50)
    monkeypatch.setattr(reference, "CACHE_MAX_BYTES", 200_000)

    payload = _payload(8)
    for index in range(2_000):
        reference._cache_write(f"key-{index:05d}", payload)

    tiles = list((tmp_path / "cache").glob("heatmap_*.json"))
    assert len(tiles) <= reference.CACHE_MAX_FILES
    assert sum(tile.stat().st_size for tile in tiles) <= reference.CACHE_MAX_BYTES
    # The newest tiles are the ones kept, and each is readable.
    assert reference._cache_read("key-01999") == payload
    assert list((tmp_path / "cache").glob(".heatmap_*.tmp")) == [], "a partial tile was left behind"


def test_the_byte_ceiling_evicts_before_the_file_ceiling(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(reference, "CACHE_DIR", tmp_path / "cache")
    monkeypatch.setattr(reference, "CACHE_MAX_FILES", 1_000)
    monkeypatch.setattr(reference, "CACHE_MAX_BYTES", 20_000)

    for index in range(200):
        reference._cache_write(f"big-{index:04d}", _payload(16))

    tiles = list((tmp_path / "cache").glob("heatmap_*.json"))
    assert 0 < len(tiles) < 200
    assert sum(tile.stat().st_size for tile in tiles) <= reference.CACHE_MAX_BYTES


def test_expired_tiles_are_removed_even_when_there_is_room(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import os

    monkeypatch.setattr(reference, "CACHE_DIR", tmp_path / "cache")
    reference._cache_write("fresh", _payload(4))
    reference._cache_write("ancient", _payload(4))
    stale = tmp_path / "cache" / "heatmap_ancient.json"
    old_time = time.time() - reference.CACHE_TTL_SECONDS - 60
    os.utime(stale, (old_time, old_time))

    assert reference.evict_disk_cache() == 1
    assert not stale.exists()
    assert (tmp_path / "cache" / "heatmap_fresh.json").exists()


# --- single flight -------------------------------------------------------


def test_one_cold_computation_per_key_under_concurrency(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from src.models.prospectivity import predict

    monkeypatch.setattr(reference, "CACHE_DIR", tmp_path / "cache")
    calls: list[float] = []

    def slow_grid(*_args: Any, grid_size: int = 4, **_kwargs: Any) -> dict[str, Any]:
        # The startup warmer may be scoring its own viewports on another thread;
        # only this test's grid size counts towards single-flight.
        if grid_size == 4:
            calls.append(time.monotonic())
            time.sleep(0.2)  # a real cold grid is ~38s
        return _payload(grid_size)

    monkeypatch.setattr(predict, "heatmap_grid", slow_grid)

    results: list[dict[str, Any]] = []
    keys_taken: set[str] = set()
    barrier = threading.Barrier(8)
    real_guard = reference._key_guard

    @contextmanager
    def watched(key: str):
        keys_taken.add(key)
        with real_guard(key):
            yield

    monkeypatch.setattr(reference, "_key_guard", watched)

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
    assert not any(key in reference._KEY_LOCKS for key in keys_taken), "a lock was left behind"
