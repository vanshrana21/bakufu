"""Spectral indices derived from the Sentinel-2 band columns."""

from __future__ import annotations

import numpy as np
import pandas as pd

#: Index columns added by `add_indices`, in order.
INDEX_COLUMNS: list[str] = [
    "mn_ratio_swir",
    "iron_ratio",
    "ferrous_ratio",
    "ndvi",
    "normalised_burn_ratio_swir",
]

_REQUIRED_BANDS: list[str] = ["b03", "b04", "b08", "b11", "b12"]


def _ratio(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    """Element-wise ratio with division-by-zero mapped to NaN."""
    denom = denominator.astype("float64").replace(0.0, np.nan)
    return numerator.astype("float64") / denom


def _normalised_difference(a: pd.Series, b: pd.Series) -> pd.Series:
    """(a - b) / (a + b), with a zero sum mapped to NaN."""
    a_f, b_f = a.astype("float64"), b.astype("float64")
    total = (a_f + b_f).replace(0.0, np.nan)
    return (a_f - b_f) / total


def add_indices(df: pd.DataFrame) -> pd.DataFrame:
    """Return `df` with the spectral index columns appended.

    Raises KeyError if a required band column is missing. Rows whose bands are
    NaN (points outside the raster) propagate NaN into every index.
    """
    missing = [band for band in _REQUIRED_BANDS if band not in df.columns]
    if missing:
        raise KeyError(f"missing band columns required for indices: {missing}")

    out = df.copy()

    # SWIR-1 / SWIR-2: manganese-oxide and clay (2200 nm) absorption proxies.
    out["mn_ratio_swir"] = _ratio(out["b11"], out["b12"])
    # Red / Green: rough ferric-iron proxy.
    out["iron_ratio"] = _ratio(out["b04"], out["b03"])
    # SWIR-1 / NIR: ferrous-mineral proxy. This slot previously held a second
    # copy of the B11/B12 ratio, so two of the five "indices" were the same
    # number and the pair drew ~48% of v5's gain between them. B11/B08 carries
    # genuinely different information rather than restating mn_ratio_swir.
    out["ferrous_ratio"] = _ratio(out["b11"], out["b08"])
    out["ndvi"] = _normalised_difference(out["b08"], out["b04"])
    out["normalised_burn_ratio_swir"] = _normalised_difference(out["b08"], out["b12"])

    return out
