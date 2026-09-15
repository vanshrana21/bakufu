"""Per-thread pool of open rasterio datasets and pyproj transformers.

Feature extraction used to open the Sentinel-2 raster, and build a new
coordinate transformer, once per point: a 32x32 heatmap paid for 1,024 opens.
Every open parses the header and takes GDAL's process-wide dataset lock, so
concurrent requests queued behind each other on that lock.

Neither object may be shared across threads: a GDAL dataset handle and a pyproj
Transformer are both single-threaded. The pool therefore keeps one of each per
worker thread, reused across calls. Handles are keyed by resolved path and file
modification time, so a raster replaced on disk is reopened, and each thread
keeps at most MAX_OPEN_PER_THREAD handles, closing the least recently used.
"""

from __future__ import annotations

import os
import threading
from collections import OrderedDict
from pathlib import Path

import rasterio
from pyproj import Transformer
from rasterio.io import DatasetReader
from rasterio.warp import transform_bounds

#: Bounds the file descriptors one worker thread can hold open.
MAX_OPEN_PER_THREAD = 8

_local = threading.local()

_BOUNDS_LOCK = threading.Lock()
_BOUNDS: dict[tuple[str, int], tuple[float, float, float, float]] = {}


def _key(path: Path | str) -> tuple[str, int]:
    resolved = os.path.realpath(path)
    return resolved, os.stat(resolved).st_mtime_ns


def dataset(path: Path | str) -> DatasetReader:
    """An open dataset for `path`, owned by the calling thread.

    Do not close it and do not hand it to another thread; the pool closes it
    when it is evicted or the file changes.
    """
    handles: OrderedDict[str, tuple[int, DatasetReader]] | None = getattr(_local, "handles", None)
    if handles is None:
        handles = _local.handles = OrderedDict()

    resolved, mtime = _key(path)
    entry = handles.get(resolved)
    if entry is not None and (entry[0] != mtime or entry[1].closed):
        entry[1].close()
        entry = None
    if entry is None:
        entry = (mtime, rasterio.open(resolved))
        handles[resolved] = entry
        while len(handles) > MAX_OPEN_PER_THREAD:
            _, (_, evicted) = handles.popitem(last=False)
            evicted.close()
    handles.move_to_end(resolved)
    return entry[1]


def transformer(source: object, target: object) -> Transformer:
    """A cached `Transformer.from_crs(source, target, always_xy=True)` for this thread."""
    cache: dict[tuple[str, str], Transformer] | None = getattr(_local, "transformers", None)
    if cache is None:
        cache = _local.transformers = {}
    key = (str(source), str(target))
    found = cache.get(key)
    if found is None:
        found = cache[key] = Transformer.from_crs(source, target, always_xy=True)
    return found


def wgs84_bounds(path: Path | str) -> tuple[float, float, float, float]:
    """(left, bottom, right, top) of a raster in EPSG:4326, computed once per file version."""
    key = _key(path)
    found = _BOUNDS.get(key)
    if found is not None:
        return found
    with rasterio.open(key[0]) as src:
        bounds = transform_bounds(src.crs, "EPSG:4326", *src.bounds)
    with _BOUNDS_LOCK:
        _BOUNDS[key] = bounds
    return bounds


def close_thread_datasets() -> None:
    """Close every handle the calling thread holds. Safe to call repeatedly."""
    handles = getattr(_local, "handles", None)
    if handles:
        for _, src in handles.values():
            src.close()
        handles.clear()
