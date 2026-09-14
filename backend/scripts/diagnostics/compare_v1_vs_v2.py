"""
STEP 4 - side-by-side comparison of Phase 2 (v1) and Phase 2.5 (v2).

Reads only saved artefacts, so it never retrains or rescores anything.

Run: python -m scripts.diagnostics.compare_v1_vs_v2
"""

from __future__ import annotations

import json
from pathlib import Path

import joblib
import numpy as np
import rasterio

from src.config.settings import settings

PROCESSED = settings.DATA_PROCESSED
RAW = settings.DATA_RAW


def _nodata_pct(path: Path) -> float | None:
    if not path.exists():
        return None
    with rasterio.open(path) as src:
        return float((src.read(1) == 0).mean() * 100.0)


def _fold_stats(path: Path) -> dict[str, object] | None:
    if not path.exists():
        return None
    rows = json.loads(path.read_text(encoding="utf-8"))
    if not rows:
        return None
    aucs = [r["auc"] for r in rows]
    prs = [r["auc_pr"] for r in rows]
    bases = [r["n_test_pos"] / r["n_test"] for r in rows]
    return {
        "mean_auc": float(np.mean(aucs)),
        "mean_auc_pr": float(np.mean(prs)),
        "mean_base": float(np.mean(bases)),
        "mean_lift": float(np.mean(prs) / np.mean(bases)),
        "auc_min": float(min(aucs)),
        "auc_max": float(max(aucs)),
        "per_fold": {r["fold"]: {"auc": r["auc"], "auc_pr": r["auc_pr"]} for r in rows},
    }


def _n_positive(path: Path) -> int | None:
    if not path.exists():
        return None
    return int(joblib.load(path).get("n_positive", 0))


def _coord_scores(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    rows = json.loads(path.read_text(encoding="utf-8"))
    return {r["label"]: r.get("score", r.get("error", "n/a")) for r in rows}


def _fmt(value: object, spec: str = ".4f") -> str:
    if value is None:
        return "n/a"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return format(value, spec)
    return str(value)[:28]


def main() -> None:
    v1 = _fold_stats(PROCESSED / "lobo_results.json")
    v2 = _fold_stats(PROCESSED / "lobo_results_v2.json")
    v3 = _fold_stats(PROCESSED / "lobo_results_v3.json")
    coords_v1 = _coord_scores(PROCESSED / "diag2_coordinate_sanity.json")
    coords_v2 = _coord_scores(PROCESSED / "diag2_coordinate_sanity_v2.json")
    coords_v3 = _coord_scores(PROCESSED / "diag2_coordinate_sanity_v3.json")

    nodata_v1 = _nodata_pct(RAW / "satellite" / "s2_nagpur_smoke_test.tif")
    nodata_v2 = _nodata_pct(RAW / "satellite" / "s2_sausar_v2.tif")
    pos_v1 = _n_positive(settings.MODELS_DIR / "prospectivity_v1.pkl")
    pos_v2 = _n_positive(settings.MODELS_DIR / "prospectivity_v2.pkl")
    pos_v3 = _n_positive(settings.MODELS_DIR / "prospectivity_v3.pkl")

    rows: list[tuple[str, str, str, str]] = [
        ("N positives", _fmt(pos_v1, "d"), _fmt(pos_v2, "d"), _fmt(pos_v3, "d")),
        ("Sausar nodata %", _fmt(nodata_v1, ".2f"), _fmt(nodata_v2, ".2f"), _fmt(nodata_v2, ".2f")),
        ("Mean AUC (LOBO)", _fmt(v1 and v1["mean_auc"]), _fmt(v2 and v2["mean_auc"]), _fmt(v3 and v3["mean_auc"])),
        ("Mean AUC-PR", _fmt(v1 and v1["mean_auc_pr"]), _fmt(v2 and v2["mean_auc_pr"]), _fmt(v3 and v3["mean_auc_pr"])),
        ("Mean lift/chance", _fmt(v1 and v1["mean_lift"], ".2f"), _fmt(v2 and v2["mean_lift"], ".2f"), _fmt(v3 and v3["mean_lift"], ".2f")),
        ("Balaghat score", _fmt(coords_v1.get("Balaghat Mn belt")), _fmt(coords_v2.get("Balaghat Mn belt")), _fmt(coords_v3.get("Balaghat Mn belt"))),
        ("Ukwa score", _fmt(coords_v1.get("Ukwa mine centre")), _fmt(coords_v2.get("Ukwa mine centre")), _fmt(coords_v3.get("Ukwa mine centre"))),
        ("Katori score", _fmt(coords_v1.get("Katori-Jhiriya XRF")), _fmt(coords_v2.get("Katori-Jhiriya XRF")), _fmt(coords_v3.get("Katori-Jhiriya XRF"))),
        (
            "Per-fold AUC spread",
            f"{v1['auc_min']:.2f}-{v1['auc_max']:.2f}" if v1 else "n/a",
            f"{v2['auc_min']:.2f}-{v2['auc_max']:.2f}" if v2 else "n/a",
            f"{v3['auc_min']:.2f}-{v3['auc_max']:.2f}" if v3 else "n/a",
        ),
    ]

    print("=" * 66)
    print("PHASE 2 (v1) vs 2.5 (v2) vs 2.7 (v3)")
    print("=" * 66)
    print("Metric".ljust(22) + "v1".rjust(13) + "v2".rjust(14) + "v3".rjust(15))
    print("-" * 66)
    for name, a, b, c in rows:
        print(name.ljust(22) + a.rjust(13) + b.rjust(14) + c.rjust(15))

    if v1 and v2:
        delta = (v3["mean_auc"] if v3 else v2["mean_auc"]) - v1["mean_auc"]
        print("")
        print(f"  mean AUC delta : {delta:+.4f}")
        best = v3["mean_auc"] if v3 else v2["mean_auc"]
        if best >= 0.70:
            verdict = "REAL SIGNAL - proceed to Phase 3 forecasting"
        elif best < v1["mean_auc"]:
            verdict = "WORSE than v1 - investigate tile coverage logic before Phase 3"
        elif 0.55 <= best <= 0.65:
            verdict = "STILL WEAK (0.55-0.65) - problem is deeper than data quantity"
        else:
            verdict = "between thresholds - judgement call"
        print(f"  verdict        : {verdict}")

        katori = coords_v3.get("Katori-Jhiriya XRF") or coords_v2.get("Katori-Jhiriya XRF")
        if isinstance(katori, (int, float)) and katori >= 0.9999:
            print("  NOTE           : Katori still saturated at 1.0000 - Elkan-Noto c-adjustment too aggressive")

    out = PROCESSED / "phase_2_7_comparison.json"
    out.write_text(
        json.dumps(
            {
                "v1": {"folds": v1, "nodata_pct": nodata_v1, "n_positive": pos_v1, "coords": coords_v1},
                "v2": {"folds": v2, "nodata_pct": nodata_v2, "n_positive": pos_v2, "coords": coords_v2},
                "v3": {"folds": v3, "nodata_pct": nodata_v2, "n_positive": pos_v3, "coords": coords_v3},
            },
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    print(f"  written to     : {out}")


if __name__ == "__main__":
    main()
