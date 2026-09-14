"""PU-learning prospectivity classifier (Elkan-Noto + XGBoost).

Label structure:
  positives   - drilled boreholes, Katori XRF samples, foreign analogues
  unlabelled  - random pixels >5 km from any borehole, treated as weak
                negatives rather than confirmed negatives

Validation is leave-one-block-out: every borehole in a block is held out
together, so a model cannot pass by memorising block identity.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
from pyproj import Transformer
from rasterio.warp import transform_bounds
from sqlalchemy import text

from src.config.settings import settings
from src.data.preprocess.compute_indices import INDEX_COLUMNS, add_indices
from src.data.preprocess.extract_features import FEATURE_COLUMNS, extract_features_bulk
from src.db.session import get_engine
from src.models.prospectivity.autoencoder import MnAutoencoder, load_autoencoder
from src.models.prospectivity.enrich_features import AE_COLUMNS, embed_points

#: Confidence in each positive, by the provenance of its grade prior.
PRIOR_TYPE_WEIGHTS: dict[str, float] = {
    "EMPIRICAL_SAMPLES": 1.0,
    "PUBLISHED_REFERENCE": 0.7,
    "EXTRAPOLATED_FROM_NEIGHBOR": 0.4,
}
XRF_WEIGHT: float = 1.0
FOREIGN_WEIGHT: float = 0.5
UNLABELLED_WEIGHT: float = 0.3

N_UNLABELLED: int = 1000
#: Fail-safe cap on rejection sampling for valid pseudo-negatives.
MAX_UNLABELLED_CANDIDATES: int = 50_000
EXCLUSION_RADIUS_M: float = 5000.0
#: Phase 2.7 Lever 3 - wider buffer, on the argument that 5 km leaves plenty of
#: geologically plausible ground being called "negative".
EXCLUSION_RADIUS_V3_M: float = 15000.0
#: Phase 2.7 Lever 2 needs far more draws, since candidates are now also
#: rejected for resembling the positive class.
MAX_UNLABELLED_CANDIDATES_V3: int = 100_000
RANDOM_SEED: int = 42

BASE_FEATURES: list[str] = FEATURE_COLUMNS + INDEX_COLUMNS
ALL_FEATURES: list[str] = BASE_FEATURES + AE_COLUMNS

MODEL_PATH: Path = settings.MODELS_DIR / "prospectivity_v1.pkl"

XGB_PARAMS: dict[str, object] = {
    "n_estimators": 500,
    "max_depth": 6,
    "learning_rate": 0.05,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "tree_method": "hist",
    "eval_metric": "aucpr",
    "objective": "binary:logistic",
    "n_jobs": 4,
    "random_state": RANDOM_SEED,
}


@dataclass
class Dataset:
    """Assembled PU training frame."""

    frame: pd.DataFrame
    features: list[str] = field(default_factory=lambda: list(ALL_FEATURES))

    @property
    def X(self) -> pd.DataFrame:  # noqa: N802 - sklearn convention
        return self.frame[self.features]

    @property
    def y(self) -> np.ndarray:
        return self.frame["label"].to_numpy()

    @property
    def w(self) -> np.ndarray:
        return self.frame["weight"].to_numpy()


def _boreholes_with_priors() -> pd.DataFrame:
    """Boreholes joined to their block prior_type."""
    sql = """
        SELECT b.id AS borehole_id, b.borehole_no, b.block_name,
               ST_Y(b.geom::geometry) AS lat, ST_X(b.geom::geometry) AS lon,
               p.prior_type
        FROM boreholes b
        LEFT JOIN block_grade_priors p ON p.block_name = b.block_name
    """
    with get_engine().connect() as conn:
        rows = conn.execute(text(sql)).all()
    return pd.DataFrame(
        rows, columns=["borehole_id", "borehole_no", "block_name", "lat", "lon", "prior_type"]
    )


def _surface_samples() -> pd.DataFrame:
    sql = """
        SELECT sample_id, block_name,
               ST_Y(geom::geometry) AS lat, ST_X(geom::geometry) AS lon
        FROM surface_samples
    """
    with get_engine().connect() as conn:
        rows = conn.execute(text(sql)).all()
    return pd.DataFrame(rows, columns=["sample_id", "block_name", "lat", "lon"])


def _foreign_deposits() -> pd.DataFrame:
    sql = """
        SELECT id AS foreign_id, deposit_name, country, deposit_type,
               ST_Y(geom::geometry) AS lat, ST_X(geom::geometry) AS lon
        FROM foreign_deposits
    """
    with get_engine().connect() as conn:
        rows = conn.execute(text(sql)).all()
    return pd.DataFrame(
        rows,
        columns=["foreign_id", "deposit_name", "country", "deposit_type", "lat", "lon"],
    )


def sample_unlabelled(
    boreholes: pd.DataFrame,
    n: int = N_UNLABELLED,
    exclusion_m: float = EXCLUSION_RADIUS_M,
    seed: int = RANDOM_SEED,
    s2_path: Path | None = None,
    max_candidates: int = MAX_UNLABELLED_CANDIDATES,
    verbose: bool = True,
    positives: pd.DataFrame | None = None,
    reject_similar: bool = False,
) -> pd.DataFrame:
    """Random *valid* in-raster points at least `exclusion_m` from every borehole.

    About a quarter of the Sausar mosaic is nodata, because Phase 1 composited
    partial swaths across a bbox wider than one MGRS tile. Sampling the bounding
    box blindly would hand the model a nodata->negative shortcut, so candidates
    landing on empty pixels are rejected here rather than filtered downstream.

    A candidate is kept only if all of these hold:
      - its B02 pixel is non-zero (0 is the mosaic's nodata sentinel, written
        across all six bands together, so B02 is a faithful proxy for the stack)
      - it falls inside the DEM's footprint, so elevation/slope/aspect resolve
      - it is at least `exclusion_m` from every borehole

    With `reject_similar` (Phase 2.7 Lever 2) a candidate is additionally
    rejected when it *looks like* a positive: its SWIR ratio sits within the
    positive band, or its elevation and slope both sit inside the positive IQR.
    A point resembling known mineralisation is not trustworthy as a negative,
    so it is discarded rather than mislabelled. `positives` supplies that
    reference distribution and is required when `reject_similar` is set.
    """
    path = s2_path or settings.s2_smoke_test
    rng = np.random.default_rng(seed)

    with rasterio.open(path) as src:
        left, bottom, right, top = src.bounds
        crs = src.crs
        # One band is enough to identify nodata and cheap to hold in memory.
        valid_mask = src.read(1) != 0
        raster_transform = src.transform
        height, width = src.height, src.width

    # Each S2 tile has its own Copernicus DEM since Phase 2.9. Validating a
    # foreign or NGDR candidate against the Nagpur DEM would reject every point
    # as "outside DEM" and starve those regions of negatives entirely.
    from src.models.prospectivity.enrich_foreign import dem_for_raster

    dem_source = dem_for_raster(path) or settings.dem_smoke_test
    with rasterio.open(dem_source) as dem:
        dem_bounds = transform_bounds(dem.crs, crs, *dem.bounds)

    to_raster = Transformer.from_crs("EPSG:4326", crs, always_xy=True)
    to_wgs = Transformer.from_crs(crs, "EPSG:4326", always_xy=True)

    bx, by = to_raster.transform(boreholes.lon.to_numpy(), boreholes.lat.to_numpy())
    bx, by = np.asarray(bx), np.asarray(by)

    dem_left, dem_bottom, dem_right, dem_top = dem_bounds
    inverse = ~raster_transform

    # Lever 2 reference distribution from the positive class.
    mn_threshold: float | None = None
    elev_lo = elev_hi = slope_lo = slope_hi = None
    if reject_similar:
        if positives is None or positives.empty:
            raise ValueError("reject_similar=True requires a non-empty `positives` frame")
        mn_values = pd.to_numeric(positives.get("mn_ratio_swir"), errors="coerce").to_numpy(dtype="float64")
        mn_values = mn_values[np.isfinite(mn_values)]
        if mn_values.size:
            mn_threshold = float(np.median(mn_values) - 0.5 * np.std(mn_values))
        elevations = pd.to_numeric(positives.get("elevation"), errors="coerce").to_numpy(dtype="float64")
        elevations = elevations[np.isfinite(elevations)]
        slopes = pd.to_numeric(positives.get("slope"), errors="coerce").to_numpy(dtype="float64")
        slopes = slopes[np.isfinite(slopes)]
        if elevations.size:
            elev_lo, elev_hi = np.percentile(elevations, [25, 75])
        if slopes.size:
            slope_lo, slope_hi = np.percentile(slopes, [25, 75])

    picked_x: list[float] = []
    picked_y: list[float] = []
    tried = 0
    rejected_nodata = 0
    rejected_dem = 0
    rejected_buffer = 0
    rejected_spectral = 0
    rejected_terrain = 0

    batch = max(n * 4, 4000)
    while len(picked_x) < n and tried < max_candidates:
        take = min(batch, max_candidates - tried)
        xs = rng.uniform(left, right, size=take)
        ys = rng.uniform(bottom, top, size=take)
        tried += take

        cols, rows = inverse * (xs, ys)
        cols = cols.astype(int)
        rows = rows.astype(int)
        in_grid = (rows >= 0) & (rows < height) & (cols >= 0) & (cols < width)

        keep = np.zeros(take, dtype=bool)
        keep[in_grid] = valid_mask[rows[in_grid], cols[in_grid]]
        rejected_nodata += int((~keep).sum())

        in_dem = (xs >= dem_left) & (xs <= dem_right) & (ys >= dem_bottom) & (ys <= dem_top)
        rejected_dem += int((keep & ~in_dem).sum())
        keep &= in_dem

        if keep.any():
            dist = np.sqrt(
                (xs[keep][:, None] - bx[None, :]) ** 2 + (ys[keep][:, None] - by[None, :]) ** 2
            )
            far_enough = dist.min(axis=1) >= exclusion_m
            rejected_buffer += int((~far_enough).sum())
            cand_x = xs[keep][far_enough]
            cand_y = ys[keep][far_enough]

            if reject_similar and cand_x.size:
                cand_lon, cand_lat = to_wgs.transform(cand_x, cand_y)
                probe = pd.DataFrame({"lon": cand_lon, "lat": cand_lat})
                features = add_indices(extract_features_bulk(probe, s2_path=path))

                mn = pd.to_numeric(features.get("mn_ratio_swir"), errors="coerce").to_numpy(dtype="float64")
                elevation = pd.to_numeric(features.get("elevation"), errors="coerce").to_numpy(dtype="float64")
                slope = pd.to_numeric(features.get("slope"), errors="coerce").to_numpy(dtype="float64")

                # Spectrally too close to the positive class to trust as negative.
                spectral_bad = np.zeros(len(probe), dtype=bool)
                if mn_threshold is not None:
                    spectral_bad = np.nan_to_num(mn, nan=-np.inf) > mn_threshold

                # Terrain matches positives on BOTH elevation and slope.
                terrain_bad = np.zeros(len(probe), dtype=bool)
                if None not in (elev_lo, elev_hi, slope_lo, slope_hi):
                    terrain_bad = (
                        (elevation >= elev_lo) & (elevation <= elev_hi)
                        & (slope >= slope_lo) & (slope <= slope_hi)
                    )
                    terrain_bad = np.nan_to_num(terrain_bad, nan=False).astype(bool)

                rejected_spectral += int(spectral_bad.sum())
                rejected_terrain += int((terrain_bad & ~spectral_bad).sum())
                ok = ~(spectral_bad | terrain_bad)
                cand_x, cand_y = cand_x[ok], cand_y[ok]

            picked_x.extend(cand_x.tolist())
            picked_y.extend(cand_y.tolist())

    if len(picked_x) < n:
        raise RuntimeError(
            f"only {len(picked_x)} valid pseudo-negatives found after {tried} candidates "
            f"(needed {n}). Rejections: nodata={rejected_nodata}, outside-DEM={rejected_dem}, "
            f"within-{exclusion_m:.0f}m-of-borehole={rejected_buffer}, "
            f"spectral-overlap={rejected_spectral}, terrain-overlap={rejected_terrain}. "
            "The raster's valid area is too small or too close to the boreholes."
        )

    n_valid = len(picked_x)
    picked_x, picked_y = picked_x[:n], picked_y[:n]
    if verbose:
        # Rejection rate is rejected/tried. The surplus beyond `n` is truncation,
        # not rejection, so it is reported separately to keep the two distinct.
        rejected = (
            rejected_nodata + rejected_dem + rejected_buffer
            + rejected_spectral + rejected_terrain
        )
        rejection_rate = (rejected / tried) * 100.0 if tried else 0.0
        print(
            f"Sampled {len(picked_x)} valid pseudo-negatives from {tried} candidates "
            f"(rejection rate {rejection_rate:.1f}%; {n_valid} passed all filters, "
            f"kept first {len(picked_x)})"
        )
        def _pct(count: int) -> str:
            return f"{count / tried * 100:.1f}%" if tried else "n/a"

        print("  rejection breakdown (share of all candidates drawn):")
        print(f"    nodata                        : {rejected_nodata:>6}  {_pct(rejected_nodata)}")
        print(f"    within {exclusion_m / 1000:.0f} km borehole buffer   : {rejected_buffer:>6}  {_pct(rejected_buffer)}")
        print(f"    outside DEM                   : {rejected_dem:>6}  {_pct(rejected_dem)}")
        if reject_similar:
            print(f"    spectral overlap w/ positives : {rejected_spectral:>6}  {_pct(rejected_spectral)}")
            print(f"    terrain overlap w/ positives  : {rejected_terrain:>6}  {_pct(rejected_terrain)}")

    lons, lats = to_wgs.transform(np.array(picked_x), np.array(picked_y))
    return pd.DataFrame({"lon": lons, "lat": lats})



#: Phase 2.9 - negatives are drawn from every region positives come from, so
#: "which raster did this point come from" stops being a usable shortcut.
NEGATIVES_PER_REGION: int = 500


def _tile_region(stem: str) -> str:
    if stem.startswith("foreign_"):
        return "foreign"
    if stem.startswith("ngdr_"):
        return "ngdr"
    return "pretrain"


def sample_unlabelled_global(
    all_positives: pd.DataFrame,
    n_per_region: int = NEGATIVES_PER_REGION,
    exclusion_m: float = EXCLUSION_RADIUS_V3_M,
    seed: int = RANDOM_SEED,
    reject_similar: bool = True,
    positives_reference: pd.DataFrame | None = None,
    verbose: bool = True,
) -> pd.DataFrame:
    """Draw pseudo-negatives proportionally from Sausar, foreign and NGDR tiles.

    Sampling only from Sausar (v2-v4) meant every negative shared one raster,
    one acquisition window and one DEM footprint while positives spanned three
    continents - so provenance alone separated the classes. Drawing negatives
    from the same tiles the positives came from removes that.

    `all_positives` supplies lon/lat for the exclusion buffer and must cover
    every positive source, not just boreholes.
    """
    tile_dir = settings.DATA_RAW / "satellite" / "unlabelled"

    # Prefer a composited _v2 tile wherever one exists - the originals are the
    # swath-gap versions that cost Phase 2.8 its dropped positives.
    ngdr_all = sorted(tile_dir.glob("ngdr_*.tif"))
    composited = {p.stem[:-3] for p in ngdr_all if p.stem.endswith("_v2")}
    ngdr_tiles = [p for p in ngdr_all if p.stem.endswith("_v2") or p.stem not in composited]
    foreign_tiles = sorted(tile_dir.glob("foreign_*.tif"))

    regions: list[tuple[str, list[Path]]] = [
        ("sausar", [settings.DATA_RAW / "satellite" / "s2_sausar_v2.tif"]),
        ("foreign", foreign_tiles),
        ("ngdr", ngdr_tiles),
    ]

    rng = np.random.default_rng(seed)
    frames: list[pd.DataFrame] = []
    summary: list[dict[str, object]] = []

    for region_index, (region, tiles) in enumerate(regions):
        tiles = [t for t in tiles if t.exists()]
        if not tiles:
            summary.append({"region": region, "tiles": 0, "valid": 0, "note": "no tiles"})
            continue

        per_tile = max(1, int(np.ceil(n_per_region / len(tiles))))
        collected: list[pd.DataFrame] = []
        drawn = 0

        for tile_index, tile in enumerate(tiles):
            if sum(len(c) for c in collected) >= n_per_region:
                break
            try:
                picked = sample_unlabelled(
                    all_positives,
                    n=per_tile,
                    exclusion_m=exclusion_m,
                    seed=seed + region_index * 1000 + tile_index,
                    s2_path=tile,
                    max_candidates=max(per_tile * 60, 4000),
                    verbose=False,
                    positives=positives_reference,
                    reject_similar=reject_similar,
                )
            except RuntimeError:
                # A tile too small, too cloudy or too close to positives to
                # yield its quota is skipped rather than failing the batch.
                continue
            drawn += per_tile
            picked = picked.assign(region=region, tile=tile.name)
            collected.append(picked)

        if collected:
            region_frame = pd.concat(collected, ignore_index=True).head(n_per_region)
            frames.append(region_frame)
            summary.append(
                {
                    "region": region,
                    "tiles": len(tiles),
                    "requested": n_per_region,
                    "valid": len(region_frame),
                }
            )
        else:
            summary.append({"region": region, "tiles": len(tiles), "requested": n_per_region, "valid": 0})

    if not frames:
        raise RuntimeError("global pseudo-negative sampling produced no points")

    result = pd.concat(frames, ignore_index=True)

    if verbose:
        print("=" * 60)
        print("GLOBAL PSEUDO-NEGATIVE SAMPLING")
        print("=" * 60)
        print("region".ljust(14) + "tiles".rjust(8) + "requested".rjust(12) + "valid".rjust(9))
        print("-" * 60)
        for entry in summary:
            print(
                str(entry["region"]).ljust(14)
                + str(entry.get("tiles", 0)).rjust(8)
                + str(entry.get("requested", 0)).rjust(12)
                + str(entry.get("valid", 0)).rjust(9)
            )
        print(f"  total negatives : {len(result)}")
        print(f"  buffer          : {exclusion_m / 1000:.0f} km around {len(all_positives)} positives")
        print(f"  reject_similar  : {reject_similar}")

    return result

def _embed_foreign_from_tiles(frame: pd.DataFrame, model: MnAutoencoder) -> pd.DataFrame:
    """Fill AE embeddings for foreign points using the unlabelled tiles.

    Foreign deposits lie outside the Sausar raster, so their features must come
    from whichever pretraining tile covers them. Deposits no tile covers keep
    NaN and are dropped downstream.
    """
    tile_dir = settings.DATA_RAW / "satellite" / "unlabelled"
    tiles = sorted(tile_dir.glob("*.tif"))
    if not tiles:
        return frame

    pending = frame.index[
        frame[AE_COLUMNS].isna().all(axis=1) & (frame["source"] == "foreign")
    ]
    for tile in tiles:
        if len(pending) == 0:
            break
        todo = frame.loc[pending, ["lon", "lat"]]
        filled = embed_points(todo, model, raster_path=tile)
        got = filled.index[filled.notna().all(axis=1)]
        if len(got) == 0:
            continue

        frame.loc[got, AE_COLUMNS] = filled.loc[got].to_numpy()
        # Pull that tile's bands too, so base features are not left empty.
        bands = add_indices(extract_features_bulk(frame.loc[got, ["lon", "lat"]], s2_path=tile))
        bands.index = got
        for column in BASE_FEATURES:
            if column in bands.columns:
                frame.loc[got, column] = bands[column].to_numpy()
        pending = pending.difference(got)

    return frame


def _merge_precomputed_foreign(frame: pd.DataFrame, path: Path) -> pd.DataFrame:
    """Swap the on-the-fly foreign rows for precomputed cluster-tile features.

    enrich_foreign already resolved which tile covers each deposit and encoded
    it, so the placeholder foreign rows assembled above are dropped and replaced
    by that parquet's rows, re-tagged with the training weight and source.
    """
    precomputed = pd.read_parquet(path)
    precomputed = precomputed.assign(
        label=1,
        weight=FOREIGN_WEIGHT,
        source="foreign",
        block_name=None,
    )
    keep = [c for c in frame.columns if c in precomputed.columns]
    domestic = frame[frame.source != "foreign"]
    return pd.concat([domestic, precomputed[keep]], ignore_index=True)


def build_dataset(
    model: MnAutoencoder | None = None,
    n_unlabelled: int = N_UNLABELLED,
    seed: int = RANDOM_SEED,
    verbose: bool = True,
    s2_path: Path | None = None,
    foreign_features_path: Path | None = None,
    exclusion_m: float = EXCLUSION_RADIUS_M,
    max_candidates: int = MAX_UNLABELLED_CANDIDATES,
    reject_similar: bool = False,
) -> Dataset:
    """Assemble positives + unlabelled with features, weights and fold keys.

    `s2_path` selects which Sausar mosaic supplies domestic features and
    pseudo-negatives. `foreign_features_path`, when given, takes foreign
    positives from a precomputed parquet (Phase 2.5's cluster-tile enrichment)
    instead of embedding them from tiles on the fly.
    """
    autoencoder = model or load_autoencoder()

    boreholes = _boreholes_with_priors()
    boreholes["label"] = 1
    boreholes["weight"] = boreholes.prior_type.map(PRIOR_TYPE_WEIGHTS).fillna(0.4)
    boreholes["source"] = "borehole"

    samples = _surface_samples()
    samples["label"] = 1
    samples["weight"] = XRF_WEIGHT
    samples["source"] = "xrf_sample"

    # Lever 2 needs the positive class's spectral/terrain distribution before
    # negatives can be screened against it, so positives are featurised first.
    positive_reference: pd.DataFrame | None = None
    if reject_similar:
        positive_points = pd.concat(
            [boreholes[["lon", "lat"]], samples[["lon", "lat"]]], ignore_index=True
        )
        positive_reference = add_indices(
            extract_features_bulk(positive_points, s2_path=s2_path)
        )

    unlabelled = sample_unlabelled(
        boreholes,
        n=n_unlabelled,
        seed=seed,
        s2_path=s2_path,
        exclusion_m=exclusion_m,
        max_candidates=max_candidates,
        positives=positive_reference,
        reject_similar=reject_similar,
    )
    unlabelled["label"] = 0
    unlabelled["weight"] = UNLABELLED_WEIGHT
    unlabelled["source"] = "unlabelled"
    # Unlabelled points carry no block; they are spread across folds instead.
    unlabelled["block_name"] = None

    foreign = _foreign_deposits()
    foreign["label"] = 1
    foreign["weight"] = FOREIGN_WEIGHT
    foreign["source"] = "foreign"
    foreign["block_name"] = None

    columns = ["lat", "lon", "label", "weight", "source", "block_name"]
    combined = pd.concat([f[columns] for f in (boreholes, samples, unlabelled, foreign)], ignore_index=True)

    combined = add_indices(extract_features_bulk(combined, s2_path=s2_path))

    embeddings = embed_points(combined, autoencoder, raster_path=s2_path)
    combined = pd.concat([combined, embeddings], axis=1)
    if foreign_features_path is None:
        combined = _embed_foreign_from_tiles(combined, autoencoder)
    else:
        combined = _merge_precomputed_foreign(combined, foreign_features_path)

    before = len(combined)
    usable = combined[AE_COLUMNS].notna().all(axis=1)
    combined = combined[usable].reset_index(drop=True)

    # Points outside a raster come back as None from Phase 1's extractors, which
    # turns whole columns object-dtype and XGBoost rejects those. Coerce to
    # float64 and leave the gaps as NaN - XGBoost handles missing values natively,
    # so DEM edge holes simply become their own split direction.
    combined[ALL_FEATURES] = combined[ALL_FEATURES].apply(
        pd.to_numeric, errors="coerce"
    ).astype("float64")

    if verbose:
        counts = combined.groupby("source").size()
        print("=" * 60)
        print("PU DATASET")
        print("=" * 60)
        print(f"  Positives (boreholes)        : {int(counts.get('borehole', 0))}")
        print(f"  Positives (XRF)              : {int(counts.get('xrf_sample', 0))}")
        print(f"  Positives (foreign, in-tile) : {int(counts.get('foreign', 0))}")
        print(f"  Pseudo-negatives (validated) : {int(counts.get('unlabelled', 0))}")
        print(f"  Total training rows          : {len(combined)}")
        print(f"  assembled rows : {before}  (dropped {before - len(combined)} outside all rasters)")
        print(f"  features       : {len(ALL_FEATURES)} ({len(BASE_FEATURES)} base + {len(AE_COLUMNS)} AE)")
        n_nan = int(combined[ALL_FEATURES].isna().sum().sum())
        print(f"  feature NaNs   : {n_nan} (left as NaN for XGBoost)")
        print(f"  dtypes         : {sorted({str(d) for d in combined[ALL_FEATURES].dtypes})}")

    return Dataset(frame=combined)
