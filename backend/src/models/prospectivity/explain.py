"""SHAP explanations for prospectivity predictions.

SHAP values are additive in the model's log-odds (margin) space:
    base_value + sum(shap_values) == raw margin
The probability is the sigmoid of that sum, so `explain_prediction` reports
both, and the test suite asserts the identity holds.

Run: python -m src.models.prospectivity.explain
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

import joblib
import matplotlib
from cachetools import LRUCache

matplotlib.use("Agg")  # headless; no display on the box this runs on
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import shap

from src.config.settings import settings
from src.models.artifact_security import load_joblib
from src.models.explainers import tree_explainer
from src.models.prospectivity.pu_xgboost import MODEL_PATH

SUMMARY_PLOT_PATH: Path = settings.DATA_PROCESSED / "shap_summary.png"

#: Bundles kept in memory, keyed by file identity. Bounded: a promotion adds a
#: new key, and without a ceiling every promotion would leak a model.
_CACHE: LRUCache[tuple[str, int, int], dict[str, Any]] = LRUCache(maxsize=3)
_CACHE_LOCK = threading.Lock()


def _identity(path: Path) -> tuple[str, int, int]:
    """Path, modification time and size: a replaced file is a different key."""
    stat = path.stat()
    return (str(path.resolve()), stat.st_mtime_ns, stat.st_size)


def load_bundle(
    model_path: Path | str = MODEL_PATH, *, production: bool = True
) -> dict[str, Any]:
    """Load and memoise the trained model bundle.

    Keyed by what is on disk, not just the path: promotion replaces the file
    the pointer names, and a path-only cache would serve the previous model for
    the life of the process.
    """
    path = Path(model_path)
    if not path.exists():
        raise FileNotFoundError(
            f"no trained model at {path} - "
            "run python -m src.models.prospectivity.train_pu_xgboost"
        )
    key = _identity(path)
    with _CACHE_LOCK:
        cached = _CACHE.get(key)
    if cached is not None:
        return cached
    if production:
        from src.models import registry

        bundle = load_joblib(path, registry_root=registry.VERSIONS_DIR)
    else:
        bundle = joblib.load(path)
    with _CACHE_LOCK:
        _CACHE[key] = bundle
    return bundle


def clear_bundle_cache() -> None:
    """Drop every loaded bundle. Used at startup and after a promotion."""
    with _CACHE_LOCK:
        _CACHE.clear()


def _explainer(bundle: dict[str, Any]) -> shap.TreeExplainer:
    return tree_explainer(bundle)


def sigmoid(x: float | np.ndarray) -> float | np.ndarray:
    return 1.0 / (1.0 + np.exp(-x))


def explain_prediction(
    features_vector: pd.Series | pd.DataFrame | np.ndarray | dict[str, float],
    model_path: Path | str = MODEL_PATH,
    top_n: int = 5,
) -> dict[str, Any]:
    """Explain one prediction.

    Returns the top contributing features with their SHAP values and actual
    values, the model base rate, and the predicted probability.
    """
    bundle = load_bundle(model_path)
    features: list[str] = bundle["features"]

    if isinstance(features_vector, dict):
        row = pd.DataFrame([features_vector])
    elif isinstance(features_vector, pd.Series):
        row = features_vector.to_frame().T
    elif isinstance(features_vector, np.ndarray):
        row = pd.DataFrame(features_vector.reshape(1, -1), columns=features)
    else:
        row = features_vector.copy()

    row = row.reindex(columns=features).astype("float64")

    explainer = _explainer(bundle)
    shap_values = np.asarray(explainer.shap_values(row))[0]
    base_value = float(np.ravel(explainer.expected_value)[0])
    margin = base_value + float(shap_values.sum())

    order = np.argsort(np.abs(shap_values))[::-1][:top_n]
    top = [
        {
            "feature": features[i],
            "shap_value": float(shap_values[i]),
            "actual_value": (None if pd.isna(row.iloc[0, i]) else float(row.iloc[0, i])),
        }
        for i in order
    ]

    return {
        "top_5_features": top,
        "base_value": base_value,
        "prediction": float(sigmoid(margin)),
        "margin": margin,
        "shap_sum": float(shap_values.sum()),
    }


def explain_batch(
    features_df: pd.DataFrame,
    model_path: Path | str = MODEL_PATH,
    plot_path: Path | str = SUMMARY_PLOT_PATH,
    make_plot: bool = True,
) -> np.ndarray:
    """SHAP values for many rows; optionally writes the summary plot."""
    bundle = load_bundle(model_path)
    features: list[str] = bundle["features"]
    frame = features_df.reindex(columns=features).astype("float64")

    explainer = _explainer(bundle)
    shap_values = np.asarray(explainer.shap_values(frame))

    if make_plot:
        plot_path = Path(plot_path)
        plot_path.parent.mkdir(parents=True, exist_ok=True)
        plt.figure()
        shap.summary_plot(shap_values, frame, show=False, max_display=20)
        plt.tight_layout()
        plt.savefig(plot_path, dpi=140, bbox_inches="tight")
        plt.close("all")

    return shap_values


def main() -> None:
    """Explain all 46 borehole training points and verify SHAP additivity."""
    from src.models.prospectivity.autoencoder import load_autoencoder
    from src.models.prospectivity.pu_xgboost import build_dataset

    bundle = load_bundle()
    dataset = build_dataset(model=load_autoencoder(), verbose=False)
    boreholes = dataset.frame[dataset.frame.source == "borehole"].reset_index(drop=True)
    X = boreholes[bundle["features"]]

    shap_values = explain_batch(X)
    margins = bundle["model"].predict(X, output_margin=True)
    explainer = _explainer(bundle)
    base_value = float(np.ravel(explainer.expected_value)[0])
    reconstructed = base_value + shap_values.sum(axis=1)
    max_error = float(np.max(np.abs(reconstructed - margins)))

    print("=" * 60)
    print("SHAP EXPLANATIONS")
    print("=" * 60)
    print(f"  rows explained     : {len(X)}")
    print(f"  base value (margin): {base_value:.5f}")
    print(f"  max additivity err : {max_error:.3e}  (base + sum(shap) vs margin)")
    print(f"  summary plot       : {SUMMARY_PLOT_PATH}")

    mean_abs = (
        pd.Series(np.abs(shap_values).mean(axis=0), index=bundle["features"])
        .sort_values(ascending=False)
        .head(10)
    )
    print("\n  Top 10 features by mean |SHAP|:")
    for name, value in mean_abs.items():
        print(f"    {name:<28s} {value:.5f}")

    example = explain_prediction(X.iloc[0])
    print(f"\n  Example (borehole 0) probability {example['prediction']:.4f}:")
    for item in example["top_5_features"]:
        print(f"    {item['feature']:<28s} shap={item['shap_value']:+.5f}  value={item['actual_value']}")


if __name__ == "__main__":
    main()
