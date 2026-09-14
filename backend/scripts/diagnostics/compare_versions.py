"""
Comprehensive comparison across all model versions (v1 .. v4).

Reads the per-fold metric JSONs and coordinate-diagnostic JSONs each phase
wrote, so the table reflects measured runs rather than remembered numbers.

Run: python -m scripts.diagnostics.compare_versions
"""

from __future__ import annotations

import json
from pathlib import Path

import joblib

from src.config.settings import settings

PROCESSED: Path = settings.DATA_PROCESSED

FOLD_FILES: dict[str, str] = {
    "v6": "lobo_results_v6.json",
    "v5": "lobo_results_v5.json",
    "v1": "lobo_results.json",
    "v2": "lobo_results_v2.json",
    "v3": "lobo_results_v3.json",
    "v4": "lobo_results_v4.json",
}
COORD_FILES: dict[str, str] = {
    "v6": "diag2_coordinate_sanity_v6.json",
    "v5": "diag2_coordinate_sanity_v5.json",
    "v1": "diag2_coordinate_sanity.json",
    "v2": "diag2_coordinate_sanity_v2.json",
    "v3": "diag2_coordinate_sanity_v3.json",
    "v4": "diag2_coordinate_sanity_v4.json",
}
MODEL_FILES: dict[str, str] = {
    "v6": "prospectivity_v6.pkl",
    "v5": "prospectivity_v5.pkl",
    "v1": "prospectivity_v1.pkl",
    "v2": "prospectivity_v2.pkl",
    "v3": "prospectivity_v3.pkl",
    "v4": "prospectivity_v4.pkl",
}
VERSIONS = ["v1", "v2", "v3", "v4", "v5", "v6"]


def _fold_stats(path: Path) -> dict[str, float] | None:
    if not path.exists():
        return None
    rows = json.loads(path.read_text(encoding="utf-8"))
    if not rows:
        return None
    aucs = [float(r["auc"]) for r in rows]
    prs = [float(r["auc_pr"]) for r in rows]
    bases = [
        float(r.get("base_rate", r["n_test_pos"] / r["n_test"])) for r in rows
    ]
    lifts = [p / b if b > 0 else float("nan") for p, b in zip(prs, bases, strict=True)]
    far = [r for r in rows if str(r["fold"]).startswith("NGDR_FAR")]
    return {
        "mean_auc": sum(aucs) / len(aucs),
        "mean_auc_pr": sum(prs) / len(prs),
        "mean_lift": sum(lifts) / len(lifts),
        "auc_min": min(aucs),
        "auc_max": max(aucs),
        "n_folds": len(rows),
        "fold5_auc": float(far[0]["auc"]) if far else None,
    }


def _coords(path: Path) -> dict[str, float | None]:
    if not path.exists():
        return {}
    rows = json.loads(path.read_text(encoding="utf-8"))
    out: dict[str, float | None] = {}
    for row in rows:
        score = row.get("score")
        out[str(row.get("label"))] = float(score) if isinstance(score, (int, float)) else None
    return out


def _n_positive(path: Path) -> int | None:
    if not path.exists():
        return None
    try:
        return int(joblib.load(path).get("n_positive"))
    except Exception:  # noqa: BLE001 - a missing key must not break the table
        return None


def _fmt(value: object, spec: str = ".4f") -> str:
    if value is None:
        return "n/a"
    if isinstance(value, (int, float)):
        return format(value, spec)
    return str(value)


def main() -> None:
    folds = {v: _fold_stats(PROCESSED / FOLD_FILES[v]) for v in VERSIONS}
    coords = {v: _coords(PROCESSED / COORD_FILES[v]) for v in VERSIONS}
    positives = {v: _n_positive(settings.MODELS_DIR / MODEL_FILES[v]) for v in VERSIONS}

    def row(label: str, getter) -> tuple[str, ...]:
        return (label, *(getter(v) for v in VERSIONS))

    rows: list[tuple[str, ...]] = [
        row("Mean AUC (CV)", lambda v: _fmt(folds[v] and folds[v]["mean_auc"])),
        row("Mean AUC-PR", lambda v: _fmt(folds[v] and folds[v]["mean_auc_pr"])),
        row("Mean lift/chance", lambda v: _fmt(folds[v] and folds[v]["mean_lift"], ".2f")),
        row("N folds", lambda v: _fmt(folds[v] and folds[v]["n_folds"], "d")),
        row("Fold 5 (NGDR only)", lambda v: _fmt((folds[v] or {}).get("fold5_auc"))),
        row("AUC spread", lambda v: f"{folds[v]['auc_min']:.2f}-{folds[v]['auc_max']:.2f}" if folds[v] else "n/a"),
        row("Balaghat score", lambda v: _fmt(coords[v].get("Balaghat Mn belt"))),
        row("Ukwa score", lambda v: _fmt(coords[v].get("Ukwa mine centre"))),
        row("Katori score", lambda v: _fmt(coords[v].get("Katori-Jhiriya XRF"))),
        row("Nagpur city score", lambda v: _fmt(coords[v].get("Nagpur city centre"))),
        row("Sandur", lambda v: _fmt(coords[v].get("Sandur, Karnataka"))),
        row("Rajasthan", lambda v: _fmt(coords[v].get("Rajasthan farmland"))),
        row("Bonai (new)", lambda v: _fmt(coords[v].get("Bonai-Keonjhar, Odisha"))),
        row("N positives", lambda v: _fmt(positives[v], "d")),
    ]

    print("=" * 80)
    print("MODEL VERSION COMPARISON")
    print("=" * 80)
    print("Metric".ljust(19) + "".join(v.rjust(10) for v in VERSIONS))
    print("-" * 80)
    for label, *values in rows:
        print(str(label).ljust(19) + "".join(str(x).rjust(10) for x in values))

    payload = {
        v: {
            "folds": folds[v],
            "coords": coords[v],
            "n_positive": positives[v],
        }
        for v in VERSIONS
    }
    out = PROCESSED / "phase_2_9_final_comparison.json"
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print("")
    print(f"  written to : {out}")


if __name__ == "__main__":
    main()
