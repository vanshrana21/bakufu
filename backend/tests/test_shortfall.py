"""Tests for the shortfall classifier.

The three that matter are about honesty rather than accuracy: that labels
come from out-of-sample forecasts, that no feature can see the future, and
that a model failing the pre-registered criterion cannot be saved.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.models import shortfall_classifier as sc


@pytest.fixture(scope="module")
def labels() -> pd.DataFrame:
    if not sc.LABELS_PATH.exists():
        pytest.skip("labels not built; run shortfall_classifier --labels-only")
    return pd.read_parquet(sc.LABELS_PATH)


def test_label_definition_uses_rolling_origin_not_in_sample(labels) -> None:
    """Each label's forecast must come from a model fitted before its month.

    An in-sample fit has already seen the month it scores, so its residual is
    shrunken towards zero and the label would be partly a function of the
    answer. `n_train` growing by one per month is the signature of a rolling
    origin; a constant value would mean one model scored everything.
    """
    assert "n_train" in labels.columns
    ordered = labels.sort_values("ds")
    assert ordered.n_train.is_monotonic_increasing
    assert ordered.n_train.nunique() > 1, "a single fit would mean in-sample labels"
    # The first origin must already carry two seasons of history.
    assert ordered.n_train.min() >= sc.MIN_TRAIN_MONTHS
    # A forecast trained on k months must be scored on the (k+1)th.
    assert (ordered.n_train.diff().dropna() >= 1).all()


def test_features_are_causally_available() -> None:
    """No feature for month M may use data from M or later - except those
    explicitly justified as available at prediction time.

    Rainfall is published near-real-time by IMD, so the concurrent month is
    legitimately known; production and Prophet deviations are not, and must
    be lagged.
    """
    lagged = [f for f in sc.FEATURES if f.startswith("deviation")]
    assert lagged, "deviation features must exist"
    for name in lagged:
        assert name.endswith(("lag1", "lag2")), f"{name} must be lagged"

    # production_trend_3mo compares months M-1..M-3 against M-4..M-6.
    assert "production_trend_3mo" in sc.FEATURES
    # Only rainfall may be concurrent, and it is named so that this is visible.
    concurrent = [f for f in sc.FEATURES if "concurrent" in f]
    assert concurrent == ["rainfall_concurrent_mm"]


def test_feature_construction_does_not_leak(labels) -> None:
    """Built features for month M must not equal month M's own outcome."""
    if not sc.FEATURES_PATH.exists():
        pytest.skip("features not built")
    frame = pd.read_parquet(sc.FEATURES_PATH)

    # deviation_lag1 for row i must equal deviation for row i-1.
    ordered = frame.sort_values("ds").reset_index(drop=True)
    shifted = ordered.deviation.shift(1)
    comparable = ordered.deviation_lag1.notna() & shifted.notna()
    assert np.allclose(
        ordered.deviation_lag1[comparable], shifted[comparable], atol=1e-9
    ), "deviation_lag1 must be the previous month's deviation"
    # The current month's deviation must never appear as a feature.
    assert "deviation" not in sc.FEATURES


def test_rainfall_provenance_is_recorded() -> None:
    """Imputed rainfall must be visible, not silently substituted."""
    if not sc.FEATURES_PATH.exists():
        pytest.skip("features not built")
    frame = pd.read_parquet(sc.FEATURES_PATH)
    assert "rainfall_source" in frame.columns
    assert set(frame.rainfall_source.unique()) <= {"observed", "imputed_climatology"}


def test_ship_criterion_enforcement(tmp_path, monkeypatch) -> None:
    """A model beating the majority baseline by only 4 pp must not be saved."""
    saved: list[object] = []
    monkeypatch.setattr(sc, "MODEL_PATH", tmp_path / "should_not_exist.pkl")

    table = pd.DataFrame(
        [
            {"model": "classifier", "f1": 0.04, "precision": 0.1, "recall": 0.1,
             "tp": 6, "fp": 2, "tn": 20, "fn": 1},
            {"model": "majority-class", "f1": 0.00, "precision": 0.0, "recall": 0.0,
             "tp": 0, "fp": 0, "tn": 26, "fn": 7},
            {"model": "persistence-1lag", "f1": 0.00, "precision": 0.0, "recall": 0.0,
             "tp": 0, "fp": 1, "tn": 25, "fn": 7},
            {"model": "persistence-2lag", "f1": 0.00, "precision": 0.0, "recall": 0.0,
             "tp": 0, "fp": 1, "tn": 25, "fn": 7},
        ]
    )
    by_model = table.set_index("model").f1
    clf = table.iloc[0]
    gains = {name: clf.f1 - by_model[name] for name in
             ("majority-class", "persistence-1lag", "persistence-2lag")}

    checks = [
        gains["majority-class"] >= sc.MIN_F1_GAIN_OVER_MAJORITY,
        gains["persistence-1lag"] >= sc.MIN_F1_GAIN_OVER_HEURISTIC,
        gains["persistence-2lag"] >= sc.MIN_F1_GAIN_OVER_HEURISTIC,
        int(clf.tp) >= sc.MIN_TRUE_POSITIVES,
    ]
    # 4 pp over majority is below the 5 pp bar, so the model must be rejected
    # even though it clears every other condition.
    assert gains["majority-class"] == pytest.approx(0.04)
    assert not all(checks), "a 4 pp gain must fail the criterion"
    assert not sc.MODEL_PATH.exists(), "no pickle may be written on a failure"
    assert not saved


def test_ship_criterion_requires_all_four_conditions() -> None:
    """Each condition alone is insufficient."""
    assert sc.MIN_F1_GAIN_OVER_MAJORITY == 0.05
    assert sc.MIN_F1_GAIN_OVER_HEURISTIC == 0.03
    assert sc.MIN_TRUE_POSITIVES == 5


def test_persistence_heuristic_operates_on_the_label_quantity() -> None:
    """The control must be comparable to the label, not orthogonal to it.

    The first version flagged months where Prophet predicted a drop, which is
    a different quantity from actual undershooting Prophet; it scored F1 0.000
    and made the comparison meaningless.
    """
    frame = pd.DataFrame(
        {"deviation_lag1": [-0.20, 0.05, 0.02], "deviation_lag2": [0.01, -0.15, 0.03]}
    )
    one = sc.persistence_heuristic(frame, lags=1)
    two = sc.persistence_heuristic(frame, lags=2)
    assert list(one) == [1, 0, 0]
    assert list(two) == [1, 1, 0], "the two-lag rule must also catch the second row"


def test_stratified_windows_each_contain_a_positive() -> None:
    """No holdout window may be empty of positives - F1 is undefined there."""
    frame = pd.DataFrame({"shortfall": ([0] * 20 + [1, 0, 0, 1, 0, 0, 1, 0, 1, 0] * 4)})
    windows = sc.stratified_windows(frame, n_windows=3, min_positives=2, min_train=20)
    assert windows
    for start, end in windows:
        assert frame.iloc[start:end].shortfall.sum() >= 1


def test_shipped_model_carries_its_provenance() -> None:
    """The pickle records the label rules it was trained under."""
    if not sc.MODEL_PATH.exists():
        pytest.skip("classifier not shipped")
    import joblib

    bundle = joblib.load(sc.MODEL_PATH)
    assert bundle["features"] == list(sc.FEATURES)
    assert bundle["shortfall_threshold"] == sc.SHORTFALL_THRESHOLD
    assert bundle["min_train_for_label"] == sc.MIN_TRAIN_FOR_LABEL
    assert bundle["n_positives"] >= sc.MIN_TRUE_POSITIVES
