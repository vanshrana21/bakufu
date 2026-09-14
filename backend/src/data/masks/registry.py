"""
Mask registry - one place that knows how to apply each mask mode.

Modes:
  none              raw model output, no filtering
  geological        Macrostrat Precambrian polygon filter
  occurrence_buffer 5 km union of per-point buffers around confirmed occurrences
  both              intersection of the two (strictest)

Masks are applied AFTER the Elkan-Noto adjustment and BEFORE the score cap,
so a kept score is capped exactly as an unmasked one would be.
"""

from __future__ import annotations

from typing import Any

VALID_MASKS: tuple[str, ...] = ("none", "geological", "occurrence_buffer", "both")

_CACHE: dict[str, Any] = {}


def _geological():
    if "geological" not in _CACHE:
        from src.data.masks.geological_mask import GeologicalMask

        _CACHE["geological"] = GeologicalMask()
    return _CACHE["geological"]


def _buffer():
    if "buffer" not in _CACHE:
        from src.data.masks.occurrence_buffer_mask import OccurrenceBufferMask

        _CACHE["buffer"] = OccurrenceBufferMask()
    return _CACHE["buffer"]


def apply_mask(lat: float, lon: float, score: float, mask: str = "none") -> tuple[float, str]:
    """Return (final_score, decision) for one point under `mask`."""
    if mask not in VALID_MASKS:
        raise ValueError(f"unknown mask {mask!r}; expected one of {VALID_MASKS}")

    if mask == "none":
        return score, "n/a"

    if mask == "geological":
        return _geological().filter_score(lat, lon, score)

    if mask == "occurrence_buffer":
        return _buffer().filter_score(lat, lon, score)

    in_basement = _geological().is_in_basement(lat, lon)
    in_buffer = _buffer().is_in_buffer(lat, lon)
    if in_basement and in_buffer:
        return score, "kept_in_basement_and_buffer"
    return 0.0, "masked_out_both"


def describe() -> list[dict[str, Any]]:
    """Metadata for GET /masks."""
    return [
        {
            "id": "none",
            "label": "No mask (raw model output)",
            "source": "n/a",
            "description": (
                "Model output without geological context filtering. Shows the "
                "false positive on Nagpur cropland."
            ),
        },
        {
            "id": "geological",
            "label": "Geological formation mask",
            "source": "macrostrat_1_5M_proxy",
            "production_source": "GSI Bhukosh 1:50K",
            "description": (
                "Restricts predictions to Precambrian metasedimentary basement, "
                "excluding Deccan Trap basalt and younger cover. At ~1:5M the "
                "boundaries are tens of km coarse, so this separates basement "
                "from trap rock but not a field from an outcrop."
            ),
            "geojson_path": (
                "data/raw/india/geology/sausar_precambrian_formations_macrostrat_proxy.geojson"
            ),
        },
        {
            "id": "occurrence_buffer",
            "label": "5 km buffer around confirmed occurrences",
            "source": "occurrence_buffer_5km",
            "description": (
                "Constrains predictions to ground within 5 km of a confirmed "
                "manganese occurrence - a union of per-point buffers, not a hull, "
                "so the geometry matches the claim. Defensible on public data "
                "alone; excludes greenfield ground by design."
            ),
            "geojson_path": "data/raw/india/geology/occurrence_buffer_5km.geojson",
        },
        {
            "id": "both",
            "label": "Geological AND occurrence buffer",
            "source": "intersection",
            "description": (
                "Strictest filter: a score survives only inside Precambrian "
                "basement AND within 5 km of a confirmed occurrence."
            ),
        },
    ]
