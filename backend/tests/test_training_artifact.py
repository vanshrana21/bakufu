"""How a training run writes its model, in src/models/prospectivity/train_pu_xgboost.py.

Two things the serving path depends on. The bundle is written by rename, so no
reader ever opens a half-written file and no run can clobber another's model
mid-write. And main() parses the arguments it is given: reading the process
command line instead crashed the Celery worker, whose own argv it would have
tried to parse.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

import src.models.prospectivity.train_pu_xgboost as train_module


class _Reached(Exception):
    """Raised in place of the real training work."""


@pytest.fixture()
def no_training(monkeypatch: pytest.MonkeyPatch) -> None:
    def stop(*_args: object, **_kwargs: object) -> None:
        raise _Reached

    monkeypatch.setattr(train_module, "build_dataset", stop)
    monkeypatch.setattr(train_module, "mlflow", _NoMlflow())


class _NoMlflow:
    """Enough of mlflow for main() to get as far as the dataset."""

    def set_tracking_uri(self, *_args: object) -> None:
        return None

    def set_experiment(self, *_args: object) -> None:
        return None


# --- arguments -----------------------------------------------------------


def test_main_does_not_read_the_process_command_line(
    monkeypatch: pytest.MonkeyPatch, no_training: None
) -> None:
    """The worker's own argv must never reach this parser."""
    monkeypatch.setattr(
        "sys.argv",
        ["celery", "-A", "src.worker.celery_app", "worker", "--queues", "training", "--concurrency", "1"],
    )
    with pytest.raises(_Reached):
        train_module.main([])


def test_the_command_line_still_works(monkeypatch: pytest.MonkeyPatch, no_training: None) -> None:
    with pytest.raises(_Reached):
        train_module.main(["--version", "v1"])
    with pytest.raises(SystemExit):
        train_module.main(["--nonsense"])


# --- the bundle is written by rename -------------------------------------


@pytest.fixture()
def tiny_dataset(dummy_features: "pd.DataFrame"):  # noqa: F821 - fixture from conftest
    import pandas as pd

    from src.models.prospectivity.pu_xgboost import ALL_FEATURES, Dataset

    frame = dummy_features.copy()
    rng = np.random.default_rng(3)
    frame["label"] = (rng.random(len(frame)) > 0.5).astype(int)
    frame.loc[frame.index[:5], "label"] = 1
    frame.loc[frame.index[5:10], "label"] = 0
    frame["weight"] = 0.8
    assert isinstance(frame, pd.DataFrame)
    return Dataset(frame=frame, features=list(ALL_FEATURES))


def test_the_bundle_lands_whole(tiny_dataset, tmp_path: Path) -> None:
    import joblib

    target = tmp_path / "prospectivity_v1.pkl"
    train_module.train_final(tiny_dataset, save_path=target, log_mlflow=False)

    assert joblib.load(target)["features"]
    assert list(tmp_path.glob(".*tmp")) == [], "a staging file was left behind"


def test_a_failed_write_leaves_the_current_model_untouched(
    tiny_dataset, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The failure that used to truncate the served bundle in place."""
    import joblib

    target = tmp_path / "prospectivity_v1.pkl"
    train_module.train_final(tiny_dataset, save_path=target, log_mlflow=False)
    before = target.read_bytes()

    def half_written(_bundle: object, path: Path) -> None:
        Path(path).write_bytes(b"truncated")
        raise OSError("disk full")

    monkeypatch.setattr(train_module.joblib, "dump", half_written)
    with pytest.raises(OSError, match="disk full"):
        train_module.train_final(tiny_dataset, save_path=target, log_mlflow=False)

    assert target.read_bytes() == before
    assert joblib.load(target)["features"]
    assert list(tmp_path.glob(".*tmp")) == []
