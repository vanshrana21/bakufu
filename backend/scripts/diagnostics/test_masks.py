"""
Nine-coordinate mask comparison against the running API.

Scores each Phase 2.9 test coordinate four ways - unmasked, geological,
occurrence buffer, and both - so the effect of each filter is visible per
location rather than only in aggregate.

Requires the API to be running with v6 loaded.

Run: python -m scripts.diagnostics.test_masks
"""

from __future__ import annotations

import json

import httpx

from src.config.settings import settings

API = "http://localhost:8000"
TIMEOUT_S = 240.0
MODES = ("none", "geological", "occurrence_buffer", "both")

POINTS: list[tuple[str, float, float, str]] = [
    ("Ukwa mine centre", 21.71, 79.79, "HIGH"),
    ("Balaghat Mn belt", 21.80, 80.20, "HIGH"),
    ("Nagpur city centre", 21.15, 79.09, "LOW"),
    ("Farmland N of Nagpur", 21.55, 79.30, "LOW-MED"),
    ("Kanhan river bed", 21.70, 80.05, "LOW"),
    ("Katori-Jhiriya XRF", 21.58, 79.86, "MED-HIGH"),
    ("Substitute control", 21.30, 79.60, "LOW"),
    ("Sandur, Karnataka", 15.10, 76.55, "HIGH"),
    ("Bonai-Keonjhar, Odisha", 21.63, 85.58, "HIGH"),
    ("Rajasthan farmland", 26.50, 74.50, "LOW"),
]


def main() -> None:
    rows: list[dict[str, object]] = []
    with httpx.Client(timeout=TIMEOUT_S) as client:
        for label, lat, lon, expected in POINTS:
            entry: dict[str, object] = {"label": label, "lat": lat, "lon": lon, "expected": expected}
            for mode in MODES:
                try:
                    response = client.post(
                        f"{API}/predict/point",
                        json={"lat": lat, "lon": lon},
                        params={"mask": mode},
                    )
                    if response.status_code != 200:
                        entry[mode] = None
                        entry[f"{mode}_note"] = f"HTTP {response.status_code}"
                    else:
                        body = response.json()
                        entry[mode] = body.get("final_score", body.get("prospectivity_score"))
                        entry[f"{mode}_decision"] = body.get("mask_decision")
                        entry["raw_score"] = body.get("raw_score")
                except Exception as exc:  # noqa: BLE001 - an error IS the answer
                    entry[mode] = None
                    entry[f"{mode}_note"] = f"{type(exc).__name__}"
            rows.append(entry)

    def cell(value: object) -> str:
        if isinstance(value, (int, float)):
            return f"{value:.4f}"
        return "n/a"

    print("=" * 92)
    print("MASK COMPARISON - v6")
    print("=" * 92)
    header = (
        "location".ljust(24)
        + "raw".rjust(10)
        + "geological".rjust(12)
        + "buffer_5km".rjust(12)
        + "both".rjust(10)
        + "  expected"
    )
    print(header)
    print("-" * 92)
    for row in rows:
        print(
            str(row["label"])[:23].ljust(24)
            + cell(row.get("none")).rjust(10)
            + cell(row.get("geological")).rjust(12)
            + cell(row.get("occurrence_buffer")).rjust(12)
            + cell(row.get("both")).rjust(10)
            + "  "
            + str(row["expected"])
        )

    print("")
    print("  mask decisions (geological / buffer / both):")
    for row in rows:
        if row.get("none") is None:
            continue
        print(
            f"    {str(row['label'])[:23]:<24}"
            f"{str(row.get('geological_decision')):<28}"
            f"{str(row.get('occurrence_buffer_decision')):<26}"
            f"{str(row.get('both_decision'))}"
        )

    scored = [r for r in rows if isinstance(r.get("none"), (int, float))]
    print("")
    for mode in MODES:
        values = [float(r[mode]) for r in scored if isinstance(r.get(mode), (int, float))]
        if not values:
            continue
        survived = sum(1 for v in values if v > 0.0)
        print(f"  {mode:<16} mean={sum(values)/len(values):.4f}  surviving={survived}/{len(values)}")

    out = settings.DATA_PROCESSED / "mask_comparison_v6.json"
    out.write_text(json.dumps(rows, indent=2, default=str), encoding="utf-8")
    print("")
    print(f"  written to : {out}")


if __name__ == "__main__":
    main()
