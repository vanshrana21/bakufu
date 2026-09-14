"""
DIAGNOSTIC 1 - does the handful of foreign positives contribute anything?

Run A: pipeline as planned (foreign positives at their configured weight).
Run B: identical, foreign weight forced to 0.0 (equivalent to excluding them).

The dataset is assembled once and re-weighted in memory, so both runs see
byte-identical features, folds and unlabelled samples - the only difference
is the foreign weight. Nothing in the Phase 2 core scripts is modified.

Run: python -m scripts.diagnostics.diag1_foreign_ablation
"""

from __future__ import annotations

import json

import mlflow
import pandas as pd

from src.config.settings import settings
from src.models.prospectivity.pu_xgboost import ALL_FEATURES, Dataset, build_dataset
from src.models.prospectivity.train_pu_xgboost import (
    EXPERIMENT,
    MLFLOW_URI,
    TOP_K,
    run_lobo_cv,
)


def _summarise(results: pd.DataFrame, label: str) -> dict[str, object]:
    summary: dict[str, object] = {
        "run": label,
        "mean_auc": float(results.auc.mean()),
        "mean_auc_pr": float(results.auc_pr.mean()),
    }
    for k in TOP_K:
        column = f"prec_at_{k}"
        if column in results and results[column].notna().any():
            summary[f"mean_prec_at_{k}"] = float(results[column].mean(skipna=True))
    return summary


def _log(results: pd.DataFrame, summary: dict[str, object], run_name: str, n_foreign: int) -> None:
    with mlflow.start_run(run_name=run_name):
        mlflow.log_params(
            {
                "diagnostic": "foreign_ablation",
                "n_foreign_positives": n_foreign,
                "n_features": len(ALL_FEATURES),
            }
        )
        mlflow.log_metrics({k: v for k, v in summary.items() if isinstance(v, (int, float))})
        for _, row in results.iterrows():
            mlflow.log_metric("fold_auc_pr", float(row.auc_pr), step=int(row.name))
        mlflow.log_dict(results.to_dict(orient="records"), "per_fold.json")


def main() -> None:
    mlflow.set_tracking_uri(MLFLOW_URI)
    mlflow.set_experiment(EXPERIMENT)

    dataset = build_dataset()
    frame = dataset.frame
    n_foreign = int((frame.source == "foreign").sum())

    print(f"\nforeign positives present in dataset: {n_foreign}")

    print("\n" + "=" * 60)
    print("RUN A - with foreign positives")
    print("=" * 60)
    results_a = run_lobo_cv(Dataset(frame=frame.copy()), log_mlflow=False)
    summary_a = _summarise(results_a, "with_foreign")
    _log(results_a, summary_a, "lobo_with_foreign", n_foreign)

    print("\n" + "=" * 60)
    print("RUN B - foreign weight forced to 0.0")
    print("=" * 60)
    frame_b = frame.copy()
    frame_b.loc[frame_b.source == "foreign", "weight"] = 0.0
    results_b = run_lobo_cv(Dataset(frame=frame_b), log_mlflow=False)
    summary_b = _summarise(results_b, "no_foreign")
    _log(results_b, summary_b, "lobo_no_foreign", 0)

    delta = summary_a["mean_auc_pr"] - summary_b["mean_auc_pr"]
    if abs(delta) < 0.02:
        verdict = "NOT CONTRIBUTING - foreign labels make no meaningful difference"
    elif abs(delta) > 0.05:
        verdict = "MATTERS - foreign labels materially change the result"
    else:
        verdict = "MARGINAL - between the 0.02 and 0.05 thresholds"

    print("\n" + "=" * 60)
    print("DIAGNOSTIC 1 RESULT")
    print("=" * 60)
    comparison = pd.DataFrame(
        {
            "fold": results_a.fold,
            "auc_pr_with_foreign": results_a.auc_pr.round(4),
            "auc_pr_no_foreign": results_b.auc_pr.round(4),
        }
    )
    comparison["delta"] = (comparison.auc_pr_with_foreign - comparison.auc_pr_no_foreign).round(4)
    print(comparison.to_string(index=False))
    print(f"\n  mean AUC-PR with foreign : {summary_a['mean_auc_pr']:.4f}")
    print(f"  mean AUC-PR no foreign   : {summary_b['mean_auc_pr']:.4f}")
    print(f"  delta                    : {delta:+.4f}")
    print(f"  verdict                  : {verdict}")

    out = settings.DATA_PROCESSED / "diag1_foreign_ablation.json"
    out.write_text(
        json.dumps(
            {
                "n_foreign": n_foreign,
                "with_foreign": {"summary": summary_a, "per_fold": results_a.to_dict(orient="records")},
                "no_foreign": {"summary": summary_b, "per_fold": results_b.to_dict(orient="records")},
                "delta_mean_auc_pr": delta,
                "verdict": verdict,
            },
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    print(f"  written to               : {out}")


if __name__ == "__main__":
    main()
