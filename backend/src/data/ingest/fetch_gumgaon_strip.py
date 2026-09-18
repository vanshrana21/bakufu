"""
Fetch a western Sentinel-2 + DEM strip so Gumgaon can be scored.

Gumgaon (21.400 N, 78.980 E) sits ~0.9 km west of the Sausar mosaic's edge
(lon 78.9888) and ~2 km west of the DEM (lon 79.0), so the API has no imagery
there. This fetches only the strip [78.93, 21.35, 79.03, 21.45], using exactly
the search parameters that built s2_sausar_v2.tif, and writes serving rasters:

  data/raw/satellite/s2_moil_operational_v1.tif = s2_sausar_v2.tif + strip
  data/raw/dem/dem_moil_operational.tif         = dem_nagpur_smoke_test.tif + strip

The training rasters are read, never modified. Wherever s2_sausar_v2 has data
its pixels are copied unchanged and the strip only fills pixels it lacks, so
every location v6 was trained on is served byte-identically. Both properties
are checked before the script reports success.

Run: python -m src.data.ingest.fetch_gumgaon_strip
"""

from __future__ import annotations

import warnings

import numpy as np
import rasterio
from pyproj import Transformer
from pystac_client import Client
from rasterio.merge import merge
from rasterio.transform import from_origin
from rasterio.warp import transform_bounds
from rasterio.windows import from_bounds

from src.config.settings import settings
from src.data.ingest.recompose_sausar import CLOUD_CEILING, DATE_RANGE, MAX_SCENES_PER_TILE
from src.data.smoke_test import BANDS, DST_CRS, FILL_TARGET, STAC_URL, TARGET_RES, composite_into

warnings.filterwarnings("ignore")

STRIP_BBOX: list[float] = [78.93, 21.35, 79.03, 21.45]
GUMGAON: tuple[float, float] = (21.400, 78.980)  # (lat, lon)

S2_TRAINING = settings.DATA_RAW / "satellite" / "s2_sausar_v2.tif"
DEM_TRAINING = settings.DATA_RAW / "dem" / "dem_nagpur_smoke_test.tif"
S2_OUT = settings.DATA_RAW / "satellite" / "s2_moil_operational_v1.tif"
DEM_OUT = settings.DATA_RAW / "dem" / "dem_moil_operational.tif"

#: The source DEM declares no nodata; the extended one needs a value for
#: pixels no tile covers, chosen well outside any real elevation.
DEM_NODATA = -9999.0


def _cloud_of(item) -> float:
    return float(item.properties.get("eo:cloud_cover", 100.0))


def _strip_grid(base) -> tuple[tuple[float, float, float, float], int, int]:
    """Strip bounds in UTM, snapped outward onto the training raster's lattice."""
    left, bottom, right, top = transform_bounds("EPSG:4326", DST_CRS, *STRIP_BBOX)
    b = base.bounds
    left = b.left + np.floor((left - b.left) / TARGET_RES) * TARGET_RES
    right = b.left + np.ceil((right - b.left) / TARGET_RES) * TARGET_RES
    top = b.top - np.floor((b.top - top) / TARGET_RES) * TARGET_RES
    bottom = b.top - np.ceil((b.top - bottom) / TARGET_RES) * TARGET_RES
    width = int(round((right - left) / TARGET_RES))
    height = int(round((top - bottom) / TARGET_RES))
    return (float(left), float(bottom), float(right), float(top)), width, height


def composite_strip(grid_bounds, width: int, height: int) -> dict[str, object]:
    """Composite the strip exactly as recompose_sausar composited the belt."""
    client = Client.open(STAC_URL)
    items = list(
        client.search(
            collections=["sentinel-2-l2a"],
            bbox=STRIP_BBOX,
            datetime=DATE_RANGE,
            query={"eo:cloud_cover": {"lt": CLOUD_CEILING}},
            limit=100,
            max_items=500,
        ).items()
    )
    if not items:
        raise RuntimeError("No Sentinel-2 scenes found over the Gumgaon strip.")

    by_tile: dict[str, list] = {}
    for item in items:
        tile = item.properties.get("mgrs:tile") or item.id.split("_")[1]
        by_tile.setdefault(tile, []).append(item)
    for tile in by_tile:
        by_tile[tile] = sorted(by_tile[tile], key=_cloud_of)[:MAX_SCENES_PER_TILE]
    tiles_sorted = sorted(by_tile, key=lambda t: _cloud_of(by_tile[t][0]))

    print(f"  {len(items)} scenes across {len(tiles_sorted)} MGRS tile(s)")
    print(f"  window {DATE_RANGE}, cloud < {CLOUD_CEILING}%, up to {MAX_SCENES_PER_TILE}/tile")

    # Scenes from another UTM zone are dropped by the CRS check below anyway;
    # filtering on the MGRS zone first avoids opening them at all. One such
    # open (43QHD B08) failed with an S3 read error and aborted the first run.
    zone = DST_CRS.split(":")[1][-2:]  # EPSG:32644 -> "44"
    off_zone = [t for t in tiles_sorted if not str(t).startswith(zone)]
    tiles_sorted = [t for t in tiles_sorted if str(t).startswith(zone)]
    if off_zone:
        print(f"  skipping off-zone MGRS tiles: {', '.join(off_zone)}")

    bands = np.zeros((len(BANDS), height, width), dtype="uint16")
    used: set[str] = set()
    skipped: set[str] = set()
    unreadable: set[str] = set()
    for index, band_key in enumerate(BANDS):
        dst = bands[index]
        for tile in tiles_sorted:
            for item in by_tile[tile]:
                asset = item.assets.get(band_key)
                if not asset:
                    continue
                block_fill = None
                for attempt in range(3):
                    try:
                        with rasterio.open(asset.href) as src:
                            if str(src.crs) != DST_CRS:
                                skipped.add(f"{item.id}:{src.crs}")
                                break
                            block_fill = composite_into(dst, src, grid_bounds)
                        break
                    except rasterio.errors.RasterioIOError as exc:
                        if attempt == 2:
                            # Recorded, not fatal: the next-cleanest scene fills in.
                            unreadable.add(f"{item.id}/{band_key}: {exc}")
                if block_fill is None:
                    continue
                used.add(f"{item.id} ({item.datetime.date()}, cloud {_cloud_of(item):.1f}%)")
                if block_fill >= FILL_TARGET:
                    break
        print(f"    {band_key}: {(dst != 0).mean() * 100:.2f}% filled")

    for entry in sorted(unreadable):
        print(f"    unreadable after 3 attempts: {entry}")
    return {"bands": bands, "scenes": sorted(used), "skipped_crs": sorted(skipped)}


def write_operational_s2(strip: np.ndarray, strip_bounds) -> dict[str, object]:
    """Training mosaic widened west; strip pixels only where it has none."""
    with rasterio.open(S2_TRAINING) as base:
        b = base.bounds
        left = min(b.left, strip_bounds[0])
        col_offset = int(round((b.left - left) / TARGET_RES))
        width = base.width + col_offset
        s_col = int(round((strip_bounds[0] - left) / TARGET_RES))
        s_row = int(round((b.top - strip_bounds[3]) / TARGET_RES))
        rows = min(strip.shape[1], base.height - s_row)
        cols = min(strip.shape[2], width - s_col)

        profile = base.profile.copy()
        profile.update(width=width, transform=from_origin(left, b.top, TARGET_RES, TARGET_RES), nodata=0)

        seam: dict[str, float] = {}
        filled_from_strip = 0
        # Written band by band into pixel-interleaved blocks, so each block is
        # rewritten once per band and the dead copies stay in the file: the
        # first run produced 889 MB for data the training mosaic stores in
        # 349 MB. Staging then copying rewrites every block exactly once.
        staging = S2_OUT.with_name(S2_OUT.stem + ".staging.tif")
        with rasterio.open(staging, "w", **profile) as out:
            for band_index in range(1, base.count + 1):
                source = base.read(band_index)
                full = np.zeros((base.height, width), dtype="uint16")
                full[:, col_offset:] = source
                block = full[s_row:s_row + rows, s_col:s_col + cols]
                patch = strip[band_index - 1, :rows, :cols]

                # Where both have data, the strip's composite and the training
                # mosaic should agree; a large ratio would show up as a seam.
                both = (block > 0) & (patch > 0)
                if both.any():
                    seam[BANDS[band_index - 1]] = float(np.median(patch[both] / block[both]))
                fill = (block == 0) & (patch > 0)
                filled_from_strip += int(fill.sum())
                block[fill] = patch[fill]

                assert np.array_equal(full[:, col_offset:], source), "training pixels changed"
                out.write(full, band_index)
            out.descriptions = base.descriptions

        from rasterio import shutil as rio_shutil

        with rasterio.Env(GDAL_CACHEMAX=1024):
            rio_shutil.copy(
                staging, S2_OUT, driver="GTiff",
                COMPRESS="DEFLATE", TILED="YES", BLOCKXSIZE=256, BLOCKYSIZE=256,
            )
        staging.unlink()

    return {"width": width, "col_offset": col_offset, "seam_ratio": seam,
            "pixels_filled_from_strip": filled_from_strip // base.count}


def write_operational_dem() -> dict[str, object]:
    """Training DEM widened west with Copernicus GLO-30 tiles."""
    client = Client.open(STAC_URL)
    items = list(client.search(collections=["cop-dem-glo-30"], bbox=STRIP_BBOX, limit=50).items())
    if not items:
        raise RuntimeError("No Copernicus DEM tiles found over the Gumgaon strip.")

    with rasterio.Env(AWS_NO_SIGN_REQUEST="YES", GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR"):
        base = rasterio.open(DEM_TRAINING)
        tiles = [rasterio.open(item.assets["data"].href) for item in items if "data" in item.assets]
        try:
            b = base.bounds
            bounds = (min(b.left, STRIP_BBOX[0]), b.bottom, b.right, b.top)
            # `first` precedence: the training DEM wins wherever it has data.
            mosaic, transform = merge([base, *tiles], bounds=bounds, res=base.res, nodata=DEM_NODATA)
            profile = base.profile.copy()
            profile.update(
                height=mosaic.shape[1], width=mosaic.shape[2], transform=transform,
                nodata=DEM_NODATA, count=1,
            )
            with rasterio.open(DEM_OUT, "w", **profile) as out:
                out.write(mosaic[0], 1)

            col_offset = int(round((b.left - bounds[0]) / base.res[0]))
            original = base.read(1)
            assert np.array_equal(
                mosaic[0, : base.height, col_offset : col_offset + base.width], original
            ), "training DEM pixels changed"
        finally:
            base.close()
            for tile in tiles:
                tile.close()

    return {"tiles": [item.id for item in items], "width": int(mosaic.shape[2])}


def _sample(path, lat: float, lon: float) -> list[float]:
    with rasterio.open(path) as src:
        x, y = Transformer.from_crs("EPSG:4326", src.crs, always_xy=True).transform(lon, lat)
        return [float(v) for v in next(src.sample([(x, y)]))]


def _nodata_pct_over_strip(path) -> float:
    with rasterio.open(path) as src:
        window = from_bounds(*transform_bounds("EPSG:4326", src.crs, *STRIP_BBOX), transform=src.transform)
        band = src.read(1, window=window, boundless=True, fill_value=0)
        return float((band == 0).mean() * 100)


def main() -> None:
    print("=" * 60)
    print("GUMGAON WESTERN STRIP")
    print("=" * 60)
    with rasterio.open(S2_TRAINING) as base:
        strip_bounds, width, height = _strip_grid(base)
    print(f"  strip grid: {width} x {height} px @ {TARGET_RES:.0f} m")

    composite = composite_strip(strip_bounds, width, height)
    s2 = write_operational_s2(composite["bands"], strip_bounds)
    dem = write_operational_dem()

    print("\nScenes used:")
    for scene in composite["scenes"]:
        print(f"    {scene}")
    print(f"  skipped (wrong CRS): {len(composite['skipped_crs'])}")
    print(f"\n  S2 out : {S2_OUT.name}  {S2_OUT.stat().st_size / 1e6:.1f} MB, width {s2['width']} (+{s2['col_offset']} cols)")
    print(f"           pixels filled from strip: {s2['pixels_filled_from_strip']:,}")
    print(f"           nodata over strip bbox: {_nodata_pct_over_strip(S2_OUT):.2f}%")
    print(f"           strip / training ratio where both have data: "
          + ", ".join(f"{k} {v:.3f}" for k, v in s2["seam_ratio"].items()))
    print(f"  DEM out: {DEM_OUT.name}  {DEM_OUT.stat().st_size / 1e6:.1f} MB, tiles {dem['tiles']}")
    print(f"  Gumgaon S2 bands : {_sample(S2_OUT, *GUMGAON)}")
    print(f"  Gumgaon elevation: {_sample(DEM_OUT, *GUMGAON)}")
    print("  training rasters unchanged: verified")


if __name__ == "__main__":
    main()
