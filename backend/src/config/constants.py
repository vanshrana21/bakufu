"""Controlled vocabularies shared by the DB models, loaders and API."""

from __future__ import annotations

from enum import StrEnum


class DepositType(StrEnum):
    """Genetic classification of a manganese occurrence."""

    SEDIMENTARY = "SEDIMENTARY"
    LATERITIC = "LATERITIC"
    BIF = "BIF"
    HYDROTHERMAL = "HYDROTHERMAL"
    UNKNOWN = "UNKNOWN"


class PriorType(StrEnum):
    """Provenance of a block-level grade prior."""

    EMPIRICAL_SAMPLES = "EMPIRICAL_SAMPLES"
    PUBLISHED_REFERENCE = "PUBLISHED_REFERENCE"
    EXTRAPOLATED_FROM_NEIGHBOR = "EXTRAPOLATED_FROM_NEIGHBOR"


#: Free-text deposit descriptions -> DepositType, used when ingesting
#: heterogeneous sources (NGDR, USGS, Geoscience Australia).
DEPOSIT_TYPE_KEYWORDS: dict[str, DepositType] = {
    "sediment": DepositType.SEDIMENTARY,
    "marine": DepositType.SEDIMENTARY,
    "black shale": DepositType.SEDIMENTARY,
    "laterit": DepositType.LATERITIC,
    "residual": DepositType.LATERITIC,
    "supergene": DepositType.LATERITIC,
    "weather": DepositType.LATERITIC,
    "bif": DepositType.BIF,
    "banded iron": DepositType.BIF,
    "gondite": DepositType.BIF,
    "metamorph": DepositType.BIF,
    "hydrotherm": DepositType.HYDROTHERMAL,
    "vein": DepositType.HYDROTHERMAL,
    "volcanogenic": DepositType.HYDROTHERMAL,
}


def classify_deposit_type(raw: str | None) -> DepositType:
    """Best-effort mapping of a free-text deposit description to a DepositType."""
    if not raw:
        return DepositType.UNKNOWN
    text = raw.strip().lower()
    for keyword, deposit_type in DEPOSIT_TYPE_KEYWORDS.items():
        if keyword in text:
            return deposit_type
    return DepositType.UNKNOWN
