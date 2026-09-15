"""src/data/raster_pool.py: per-thread handle reuse, isolation, refresh and eviction."""

from __future__ import annotations

import os
import threading
from pathlib import Path

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin

from src.data import raster_pool


def _write_raster(path: Path, value: int) -> Path:
    data = np.full((1, 4, 4), value, dtype="uint16")
    with rasterio.open(
        path, "w", driver="GTiff", width=4, height=4, count=1, dtype="uint16",
        crs="EPSG:32644", transform=from_origin(300000, 2400000, 20, 20),
    ) as dst:
        dst.write(data)
    return path


@pytest.fixture(autouse=True)
def _clean_pool():
    raster_pool.close_thread_datasets()
    yield
    raster_pool.close_thread_datasets()


def test_same_thread_reuses_one_handle(tmp_path: Path) -> None:
    path = _write_raster(tmp_path / "a.tif", 7)
    first = raster_pool.dataset(path)
    assert raster_pool.dataset(path) is first
    assert int(first.read(1)[0, 0]) == 7


def test_threads_never_share_a_handle(tmp_path: Path) -> None:
    path = _write_raster(tmp_path / "a.tif", 7)
    mine = raster_pool.dataset(path)
    seen: list[object] = []
    worker = threading.Thread(target=lambda: seen.append(raster_pool.dataset(path)))
    worker.start()
    worker.join()
    assert seen and seen[0] is not mine


def test_a_replaced_file_is_reopened(tmp_path: Path) -> None:
    path = _write_raster(tmp_path / "a.tif", 7)
    old = raster_pool.dataset(path)
    _write_raster(path, 9)
    stat = os.stat(path)
    os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000_000))
    fresh = raster_pool.dataset(path)
    assert fresh is not old and old.closed
    assert int(fresh.read(1)[0, 0]) == 9


def test_least_recently_used_handles_are_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(raster_pool, "MAX_OPEN_PER_THREAD", 2)
    paths = [_write_raster(tmp_path / f"{i}.tif", i) for i in range(3)]
    first = raster_pool.dataset(paths[0])
    raster_pool.dataset(paths[1])
    raster_pool.dataset(paths[2])
    assert first.closed


def test_transformer_is_cached_per_thread() -> None:
    one = raster_pool.transformer("EPSG:4326", "EPSG:32644")
    assert raster_pool.transformer("EPSG:4326", "EPSG:32644") is one
    seen: list[object] = []
    worker = threading.Thread(target=lambda: seen.append(raster_pool.transformer("EPSG:4326", "EPSG:32644")))
    worker.start()
    worker.join()
    assert seen[0] is not one


def test_wgs84_bounds_match_a_direct_read(tmp_path: Path) -> None:
    from rasterio.warp import transform_bounds

    path = _write_raster(tmp_path / "a.tif", 1)
    with rasterio.open(path) as src:
        expected = transform_bounds(src.crs, "EPSG:4326", *src.bounds)
    assert raster_pool.wgs84_bounds(path) == pytest.approx(expected)
