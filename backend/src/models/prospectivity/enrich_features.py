"""Append autoencoder embeddings to the Phase 1 training set.

The autoencoder is trained on 60 m unlabelled tiles, but the Sausar smoke-test
raster is 20 m. Patches are therefore read at a matched 60 m ground sample
distance (a 48x48 window of 20 m pixels averaged down to 16x16) so the encoder
sees the same spatial scale it was trained on.

Run: python -m src.models.prospectivity.enrich_features
"""

from __future__ import annotations

import argparse

from pathlib import Path

import numpy as np
import pandas as pd
from rasterio.enums import Resampling
from rasterio.windows import Window

from src.config.settings import settings
from src.data import raster_pool
from src.models.prospectivity.autoencoder import (
    BOTTLENECK_DIM,
    PATCH_SIZE,
    S2_SCALE,
    MnAutoencoder,
    extract_features,
    load_autoencoder,
)

#: Ground sample distance the autoencoder was trained at.
TARGET_GSD_M: float = 60.0

AE_COLUMNS: list[str] = [f"ae_{i:02d}" for i in range(BOTTLENECK_DIM)]

V1_PATH: Path = settings.DATA_PROCESSED / "training_set_v1.parquet"
V2_PATH: Path = settings.DATA_PROCESSED / "training_set_v2.parquet"


def read_patch(
    lon: float,
    lat: float,
    raster_path: Path | str | None = None,
    patch_size: int = PATCH_SIZE,
    target_gsd_m: float = TARGET_GSD_M,
) -> np.ndarray | None:
    """Read a scale-matched patch centred on a WGS84 point.

    Returns a (bands, patch_size, patch_size) float32 array scaled to [0, 1],
    or None if the point falls outside the raster.
    """
    path = Path(raster_path) if raster_path is not None else settings.s2_smoke_test
    # Pooled per thread: this runs once per point, so a fresh open and a fresh
    # transformer here cost 1,024 of each for one 32x32 heatmap.
    src = raster_pool.dataset(path)
    x, y = raster_pool.transformer("EPSG:4326", src.crs).transform(lon, lat)
    left, bottom, right, top = src.bounds
    if not (left <= x <= right and bottom <= y <= top):
        return None

    native_res = abs(src.transform.a)
    # How many native pixels span one patch at the target GSD.
    span_px = patch_size * (target_gsd_m / native_res)
    row, col = src.index(x, y)
    half = span_px / 2.0
    window = Window(col - half, row - half, span_px, span_px)

    # Boundless on purpose, even for interior windows: a plain read differs for
    # windows touching nodata, which would silently change the embeddings.
    patch = src.read(
        window=window,
        out_shape=(src.count, patch_size, patch_size),
        resampling=Resampling.average,
        boundless=True,
        fill_value=0,
    ).astype("float32")

    return np.clip(patch / S2_SCALE, 0.0, 1.0)


def embed_points(
    points: pd.DataFrame,
    model: MnAutoencoder,
    raster_path: Path | str | None = None,
    lon_col: str = "lon",
    lat_col: str = "lat",
) -> pd.DataFrame:
    """Encode every point into a 64-dim embedding.

    Points outside the raster get NaN embeddings; callers decide whether to
    drop them. Returns a frame indexed like `points` with AE_COLUMNS.
    """
    patches: list[np.ndarray | None] = [
        read_patch(float(r[lon_col]), float(r[lat_col]), raster_path)
        for _, r in points.iterrows()
    ]

    valid = [i for i, p in enumerate(patches) if p is not None]
    out = np.full((len(points), BOTTLENECK_DIM), np.nan, dtype="float32")
    if valid:
        batch = np.stack([patches[i] for i in valid])
        out[valid] = extract_features(batch, model)

    return pd.DataFrame(out, columns=AE_COLUMNS, index=points.index)


def enrich(
    v1_path: Path = V1_PATH,
    v2_path: Path = V2_PATH,
    raster_path: Path | str | None = None,
    ae_model_path: Path | None = None,
) -> pd.DataFrame:
    """Attach AE embeddings to training_set_v1 and write v2."""
    base = pd.read_parquet(v1_path)
    model = load_autoencoder(ae_model_path) if ae_model_path else load_autoencoder()

    embeddings = embed_points(base, model, raster_path=raster_path)
    enriched = pd.concat([base, embeddings], axis=1)

    v2_path.parent.mkdir(parents=True, exist_ok=True)
    enriched.to_parquet(v2_path, index=False)

    n_missing = int(embeddings.isna().all(axis=1).sum())
    print("=" * 60)
    print("TRAINING SET v2 (autoencoder-enriched)")
    print("=" * 60)
    print(f"  path            : {v2_path}")
    print(f"  rows enriched   : {len(enriched) - n_missing} / {len(enriched)}")
    print(f"  outside raster  : {n_missing}")
    print(f"  columns         : {base.shape[1]} -> {enriched.shape[1]}  (+{len(AE_COLUMNS)} AE dims)")
    print(f"  feature dim     : 14 original + {BOTTLENECK_DIM} AE = {14 + BOTTLENECK_DIM}")
    print(f"  AE nulls        : {int(embeddings.isna().sum().sum())}")
    print(f"  embedding range : [{np.nanmin(embeddings.values):.3f}, {np.nanmax(embeddings.values):.3f}]")
    return enriched


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--s2-path", default=None, help="Sentinel-2 raster to read patches from")
    parser.add_argument("--input", default=None, help="Input training-set parquet")
    parser.add_argument("--output", default=None, help="Output parquet path")
    parser.add_argument("--ae-model", default=None, help="Autoencoder checkpoint to encode with")
    args = parser.parse_args()
    enrich(
        v1_path=Path(args.input) if args.input else V1_PATH,
        v2_path=Path(args.output) if args.output else V2_PATH,
        raster_path=args.s2_path,
        ae_model_path=Path(args.ae_model) if args.ae_model else None,
    )


if __name__ == "__main__":
    main()
