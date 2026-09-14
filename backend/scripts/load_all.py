"""Run every Phase 1 loader in dependency order and print final table counts.

Run with:  python scripts/load_all.py
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import func, select  # noqa: E402

from src.data.ingest.load_boreholes import load_boreholes  # noqa: E402
from src.data.ingest.load_foreign import load_foreign  # noqa: E402
from src.data.ingest.load_ngdr_bundle import load_ngdr_bundle  # noqa: E402
from src.data.ingest.load_priors import load_priors  # noqa: E402
from src.data.ingest.load_surface_samples import load_surface_samples  # noqa: E402
from src.db.models import (  # noqa: E402
    BlockGradePrior,
    Borehole,
    ForeignDeposit,
    NgdrNational,
    Prediction,
    SurfaceSample,
)
from src.db.session import SessionLocal  # noqa: E402

# Priors load before surface samples because surface_samples.block_name is an FK
# onto block_grade_priors.block_name.
LOADERS: list[tuple[str, object]] = [
    ("boreholes", load_boreholes),
    ("block_grade_priors", load_priors),
    ("surface_samples", load_surface_samples),
    ("foreign_deposits", load_foreign),
    ("ngdr_national", load_ngdr_bundle),
]

TABLES = [
    ("boreholes", Borehole),
    ("block_grade_priors", BlockGradePrior),
    ("surface_samples", SurfaceSample),
    ("foreign_deposits", ForeignDeposit),
    ("ngdr_national", NgdrNational),
    ("predictions", Prediction),
]


def main() -> int:
    inserted: dict[str, int] = {}
    failures: dict[str, str] = {}

    for name, loader in LOADERS:
        print("\n" + "=" * 60)
        print(f"LOADING {name}")
        print("=" * 60)
        started = time.perf_counter()
        try:
            inserted[name] = loader()  # type: ignore[operator]
        except Exception as exc:  # noqa: BLE001 - one failure must not hide the rest
            failures[name] = f"{type(exc).__name__}: {exc}"
            inserted[name] = 0
            print(f"  LOADER FAILED: {failures[name]}")
        print(f"  elapsed: {time.perf_counter() - started:.1f}s")

    print("\n" + "=" * 60)
    print("FINAL TABLE COUNTS")
    print("=" * 60)
    with SessionLocal() as db:
        for table_name, model in TABLES:
            total = db.scalar(select(func.count()).select_from(model)) or 0
            added = inserted.get(table_name)
            suffix = f"  (+{added} this run)" if added is not None else ""
            print(f"  {table_name:22s} {total:6d}{suffix}")

    if failures:
        print("\nFAILED LOADERS:")
        for name, message in failures.items():
            print(f"  {name}: {message}")
        return 1
    print("\nAll loaders completed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
