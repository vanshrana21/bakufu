"""Load block-level grade priors into the block_grade_priors table.

The source CSV carries no prior_type / n_samples columns, so both are
inferred from the `source` and `notes` text (see `infer_prior_type`).

Run with:  python -m src.data.ingest.load_priors
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.config.constants import PriorType
from src.config.settings import settings
from src.data.ingest import open_session, report, to_float, to_int, to_str
from src.db.models import BlockGradePrior

SOURCE_CSV: Path = settings.DATA_RAW / "india" / "block_grade_priors.csv"

_EMPIRICAL_HINTS = ("xrf", "surface sample", "samples", "assay", "analysed")
_EXTRAPOLATED_HINTS = ("interpolated", "extrapolat", "adjacent", "extension of", "aggregate")

_N_SAMPLES_RE = re.compile(r"\b(?:n\s*=\s*|)(\d+)\s*(?:surface\s+)?samples?\b", re.IGNORECASE)


def infer_prior_type(source: str | None, notes: str | None) -> PriorType:
    """Classify a prior's provenance from its citation and notes text."""
    text = f"{source or ''} {notes or ''}".lower()
    if any(hint in text for hint in _EMPIRICAL_HINTS):
        return PriorType.EMPIRICAL_SAMPLES
    if any(hint in text for hint in _EXTRAPOLATED_HINTS):
        return PriorType.EXTRAPOLATED_FROM_NEIGHBOR
    return PriorType.PUBLISHED_REFERENCE


def infer_n_samples(notes: str | None) -> int | None:
    """Pull an explicit sample count out of the notes text, if one is stated."""
    if not notes:
        return None
    match = _N_SAMPLES_RE.search(notes)
    return int(match.group(1)) if match else None


def load_priors(csv_path: Path = SOURCE_CSV, session: Session | None = None) -> int:
    """Insert block grade priors, skipping block_names already stored."""
    db, owns = open_session(session)
    loaded = skipped = errors = 0
    try:
        df = pd.read_csv(csv_path)
        existing: set[str] = set(db.scalars(select(BlockGradePrior.block_name)).all())

        for idx, row in df.iterrows():
            try:
                block_name = to_str(row.get("block_name"))
                if not block_name:
                    print(f"  row {idx}: missing block_name - skipped")
                    errors += 1
                    continue
                if block_name in existing:
                    skipped += 1
                    continue

                source = to_str(row.get("source"))
                notes = to_str(row.get("notes"))
                prior_type = to_str(row.get("prior_type")) or infer_prior_type(source, notes).value
                n_samples = to_int(row.get("n_samples"))
                if n_samples is None:
                    n_samples = infer_n_samples(notes)

                db.add(
                    BlockGradePrior(
                        block_name=block_name,
                        district=to_str(row.get("district"), "UNKNOWN"),
                        state=to_str(row.get("state"), "UNKNOWN"),
                        mn_pct_min=to_float(row.get("mn_pct_min")),
                        mn_pct_max=to_float(row.get("mn_pct_max")),
                        mn_pct_typ=to_float(row.get("mn_pct_typ")),
                        fe_pct_min=to_float(row.get("fe_pct_min")),
                        fe_pct_max=to_float(row.get("fe_pct_max")),
                        sio2_pct_min=to_float(row.get("sio2_pct_min")),
                        sio2_pct_max=to_float(row.get("sio2_pct_max")),
                        al2o3_pct_min=to_float(row.get("al2o3_pct_min")),
                        al2o3_pct_max=to_float(row.get("al2o3_pct_max")),
                        p_pct_min=to_float(row.get("p_pct_min")),
                        p_pct_max=to_float(row.get("p_pct_max")),
                        ore_class=to_str(row.get("ore_class")),
                        host_formation=to_str(row.get("host_formation")),
                        source=source,
                        notes=notes,
                        prior_type=prior_type,
                        n_samples=n_samples,
                    )
                )
                existing.add(block_name)
                loaded += 1
            except Exception as exc:  # noqa: BLE001
                errors += 1
                print(f"  row {idx}: {type(exc).__name__}: {exc}")

        db.commit()
    finally:
        if owns:
            db.close()

    report(loaded, skipped, errors, str(csv_path))
    return loaded


if __name__ == "__main__":
    load_priors()
