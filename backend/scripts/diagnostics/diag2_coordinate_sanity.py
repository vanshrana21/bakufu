"""
DIAGNOSTIC 2 - does the model discriminate across six known locations?

Calls the live /predict/point endpoint (API must be running) and prints the
score for each coordinate beside its expected direction.

Run: python -m scripts.diagnostics.diag2_coordinate_sanity
"""

from __future__ import annotations

import argparse
import json

import httpx

from src.config.settings import settings

API = "http://localhost:8000"
TIMEOUT_S = 240.0

#: (label, lat, lon, expected direction)
POINTS: list[tuple[str, float, float, str]] = [
    ("Ukwa mine centre", 21.71, 79.79, "HIGH"),
    ("Balaghat Mn belt", 21.80, 80.20, "HIGH"),
    ("Nagpur city centre", 21.15, 79.09, "LOW"),
    ("Farmland N of Nagpur", 21.55, 79.30, "LOW-MED"),
    ("Kanhan river bed", 21.70, 80.05, "LOW"),
    ("Katori-Jhiriya XRF", 21.58, 79.86, "MED-HIGH"),
    # Nagpur city sits below the mosaic's southern edge (lat 21.2886) in both
    # v1 and v2, so this in-coverage point stands in as the urban/low control.
    ("Substitute control", 21.30, 79.60, "LOW"),
    # Phase 2.8 generalisation probes - all outside the Sausar mosaic, scored
    # via whichever national tile covers them.
    ("Sandur, Karnataka", 15.10, 76.55, "HIGH"),
    ("Bonai-Keonjhar, Odisha", 21.63, 85.58, "HIGH"),
    ("Rajasthan farmland", 26.50, 74.50, "LOW"),
]


def main(out_name: str = "diag2_coordinate_sanity.json") -> None:
    rows: list[dict[str, object]] = []
    with httpx.Client(timeout=TIMEOUT_S) as client:
        for label, lat, lon, expected in POINTS:
            entry: dict[str, object] = {
                "label": label,
                "lat": lat,
                "lon": lon,
                "expected": expected,
            }
            try:
                response = client.post(f"{API}/predict/point", json={"lat": lat, "lon": lon})
                if response.status_code != 200:
                    entry["error"] = f"HTTP {response.status_code}: {response.text[:160]}"
                else:
                    body = response.json()
                    entry["score"] = body.get("prospectivity_score")
                    entry["type"] = body.get("predicted_type")
                    entry["uncertainty"] = body.get("uncertainty")
                    top = body.get("shap_top5") or []
                    entry["top_feature"] = top[0].get("feature") if top else None
            except Exception as exc:  # noqa: BLE001 - an error IS the answer here
                entry["error"] = f"{type(exc).__name__}: {exc}"
            rows.append(entry)

    print("=" * 78)
    print("DIAGNOSTIC 2 - COORDINATE SANITY CHECK")
    print("=" * 78)
    header = "location".ljust(24) + "lat".rjust(7) + "lon".rjust(7) + "score".rjust(9) + "expected".rjust(11) + "  type"
    print(header)
    print("-" * 78)
    for r in rows:
        base = str(r["label"]).ljust(24) + f"{r['lat']:>7.2f}" + f"{r['lon']:>7.2f}"
        if "error" in r:
            print(base + "    ERROR" + str(r["expected"]).rjust(11) + "  " + str(r["error"]))
        else:
            score = r["score"]
            score_text = f"{score:.4f}" if isinstance(score, (int, float)) else str(score)
            print(base + score_text.rjust(9) + str(r["expected"]).rjust(11) + "  " + str(r.get("type")))

    scored = [r for r in rows if isinstance(r.get("score"), (int, float))]
    if len(scored) >= 2:
        values = [float(r["score"]) for r in scored]
        spread = max(values) - min(values)
        print(f"\n  score spread : {spread:.4f}  (min {min(values):.4f}, max {max(values):.4f})")
        if spread < 0.05:
            print("  ASSESSMENT   : NOT DISCRIMINATING - all six scores are effectively identical")
        else:
            highs = [float(r["score"]) for r in scored if r["expected"] in ("HIGH", "MED-HIGH")]
            lows = [float(r["score"]) for r in scored if r["expected"] == "LOW"]
            if highs and lows:
                mean_high = sum(highs) / len(highs)
                mean_low = sum(lows) / len(lows)
                print(f"  mean HIGH-ish : {mean_high:.4f}")
                print(f"  mean LOW      : {mean_low:.4f}")
                verdict = "ORDERING CORRECT" if mean_high > mean_low else "ORDERING INVERTED"
                print(f"  ASSESSMENT    : {verdict}")

    out = settings.DATA_PROCESSED / out_name
    out.write_text(json.dumps(rows, indent=2, default=str), encoding="utf-8")
    print(f"  written to    : {out}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="diag2_coordinate_sanity.json", help="filename under data/processed")
    main(parser.parse_args().output)
