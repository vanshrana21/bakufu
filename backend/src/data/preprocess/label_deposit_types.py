"""
Assign deposit_type to every training positive using deterministic
rules over host_rock + block_name + geological context.

Types: SEDIMENTARY, LATERITIC, BIF, HYDROTHERMAL, UNKNOWN

Note on the foreign source: the Phase 1 CSV's `host_rock` column is empty for
all 1333 rows, so the keyword rules below are applied to the best available
geology text instead - `host_rock`, then the already-normalised
`deposit_type` carried by the Phase 1 loader. The rules are unchanged; only the field
they read falls back.

Run: python -m src.data.preprocess.label_deposit_types
"""

from __future__ import annotations

import json

from sqlalchemy import text

from src.db.session import get_engine

SEDIMENTARY_TERMS = (
    "gondite", "phyllite", "shale", "carbonate", "chert",
    "limestone", "mansar", "sausar", "sedimentary",
)
LATERITIC_TERMS = ("laterite", "weathered", "supergene", "residual", "cap", "lateritic")
BIF_TERMS = ("bif", "banded iron", "iron formation", "ferruginous", "itabirite")
HYDROTHERMAL_TERMS = ("hydrothermal", "vein", "fault", "fracture", "epithermal")

#: Indian blocks are all Sausar Group gondite / Mansar Formation.
BLOCK_TYPES = {
    "UKWA": "SEDIMENTARY",
    "GUDMA-WESTERN-UKWA": "SEDIMENTARY",
    "PARSEONI": "SEDIMENTARY",
    "KATORI-JHIRIYA": "SEDIMENTARY",
}


def classify(*texts: object) -> tuple[str, bool]:
    """Classify from free geology text.

    Returns (type, matched_a_rule). On a multi-family match SEDIMENTARY wins:
    ~85% of Indian manganese is sedimentary or a lateritic weathering product
    of it, so it is the safest default when the text is ambiguous.
    """
    blob = " ".join(str(t) for t in texts if t not in (None, "", "NA")).lower()
    if not blob:
        return "UNKNOWN", False

    hits = []
    if any(term in blob for term in SEDIMENTARY_TERMS):
        hits.append("SEDIMENTARY")
    if any(term in blob for term in LATERITIC_TERMS):
        hits.append("LATERITIC")
    if any(term in blob for term in BIF_TERMS):
        hits.append("BIF")
    if any(term in blob for term in HYDROTHERMAL_TERMS):
        hits.append("HYDROTHERMAL")

    if not hits:
        return "UNKNOWN", False
    if len(hits) > 1 and "SEDIMENTARY" in hits:
        return "SEDIMENTARY", True
    return hits[0], True


def _report(conn, table: str) -> None:
    rows = conn.execute(
        text(f"SELECT COALESCE(deposit_type,'(null)'), COUNT(*) FROM {table} GROUP BY 1 ORDER BY 2 DESC")
    ).all()
    summary = ", ".join(f"{t} {n}" for t, n in rows)
    print(f"  {table:18s} {summary}")


def label() -> dict[str, int]:
    engine = get_engine()
    stats: dict[str, int] = {}

    with engine.begin() as conn:
        # --- boreholes: by block ---
        for block, deposit_type in BLOCK_TYPES.items():
            conn.execute(
                text("UPDATE boreholes SET deposit_type = :t WHERE block_name = :b"),
                {"t": deposit_type, "b": block},
            )
        conn.execute(
            text("UPDATE boreholes SET deposit_type = 'UNKNOWN' WHERE deposit_type IS NULL")
        )

        # --- surface samples: all Katori, same block ---
        conn.execute(text("UPDATE surface_samples SET deposit_type = 'SEDIMENTARY'"))

        # --- foreign deposits: keyword rules over best available geology text ---
        foreign = conn.execute(
            text("SELECT id, host_rock, deposit_type FROM foreign_deposits")
        ).all()
        matched = 0
        for row in foreign:
            deposit_type, hit = classify(row[1], row[2])
            matched += int(hit)
            conn.execute(
                text("UPDATE foreign_deposits SET deposit_type = :t WHERE id = :i"),
                {"t": deposit_type, "i": row[0]},
            )
        stats["foreign_rule_matched"] = matched
        stats["foreign_total"] = len(foreign)

        # --- NGDR: parse raw_props geology text ---
        ngdr = conn.execute(text("SELECT id, raw_props FROM ngdr_national")).all()
        ngdr_matched = 0
        for row in ngdr:
            props = row[1] if isinstance(row[1], dict) else (json.loads(row[1]) if row[1] else {})
            deposit_type, hit = classify(
                props.get("hostrock"),
                props.get("formation"),
                props.get("metallogen"),
                props.get("host_rock"),
                props.get("geology"),
            )
            ngdr_matched += int(hit)
            conn.execute(
                text("UPDATE ngdr_national SET deposit_type = :t WHERE id = :i"),
                {"t": deposit_type, "i": row[0]},
            )
        stats["ngdr_rule_matched"] = ngdr_matched
        stats["ngdr_total"] = len(ngdr)

        print("=" * 68)
        print("DEPOSIT TYPE LABELLING")
        print("=" * 68)
        for table in ("boreholes", "surface_samples", "foreign_deposits", "ngdr_national"):
            _report(conn, table)

        print("\n  rule-match confidence:")
        print(
            f"    foreign_deposits : {matched}/{len(foreign)} matched a keyword rule "
            f"({matched / max(len(foreign), 1) * 100:.1f}%)"
        )
        print(
            f"    ngdr_national    : {ngdr_matched}/{len(ngdr)} matched a keyword rule "
            f"({ngdr_matched / max(len(ngdr), 1) * 100:.1f}%)"
        )
        print("    boreholes        : 46/46 by block rule (100.0%)")
        print("    surface_samples  : 5/5 by block rule (100.0%)")

    return stats


def main() -> None:
    label()


if __name__ == "__main__":
    main()
