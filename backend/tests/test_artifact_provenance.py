"""A model, its encoder, its raster and its metrics are one scientific release.

Treating them as independent files is what lets a result change without its
version changing: the same bundle scored under a different autoencoder is a
different model, because 64 of its 78 features ARE that encoder's latent space,
and they keep their names (ae_0 … ae_63) while meaning something else.

Two defences, tested here. A bundle records the digests of the raster and the
encoder it was trained on, and inference refuses to score when either has
drifted. And a bundle that records nothing is served but reported as unverified,
so an unbound model never looks like a checked one.
"""

from __future__ import annotations

import json
from pathlib import Path

import joblib
import pytest

from src.models import registry
from src.models.prospectivity import predict as predict_module


# --- provenance binding at inference -------------------------------------


@pytest.fixture()
def bundle_with_provenance(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """A bundle that names a raster and an encoder, both of which exist."""
    raster = tmp_path / "s2.tif"
    raster.write_bytes(b"raster bytes")
    encoder = tmp_path / "autoencoder_v1.pt"
    encoder.write_bytes(b"encoder bytes")

    def build(*, raster_hash: str | None = None, encoder_hash: str | None = None) -> dict:
        return {
            "model": object(),
            "features": ["b11"],
            "elkan_noto_c": 0.8,
            "provenance": {
                "schema": "prospectivity-provenance-v1",
                "training_raster": {
                    "path": str(raster),
                    "sha256": raster_hash or predict_module._sha256(raster),
                },
                "encoder": {
                    "path": str(encoder),
                    "sha256": encoder_hash or predict_module._sha256(encoder),
                },
                "training_seed": 42,
            },
        }

    monkeypatch.setattr(predict_module, "ACTIVE_S2_PATH", raster)
    monkeypatch.setattr(predict_module, "ACTIVE_AE_PATH", encoder)
    return build


def test_a_bundle_scores_when_its_recorded_inputs_are_the_ones_serving_it(
    bundle_with_provenance,
) -> None:
    predict_module._verify_provenance(bundle_with_provenance())  # must not raise


def test_a_changed_encoder_stops_inference_rather_than_scoring_with_it(
    bundle_with_provenance,
) -> None:
    """The failure this exists for: same feature NAMES, different meaning."""
    drifted = bundle_with_provenance(encoder_hash="0" * 64)
    with pytest.raises(RuntimeError, match="provenance mismatch for encoder"):
        predict_module._verify_provenance(drifted)


def test_a_changed_training_raster_stops_inference_too(bundle_with_provenance) -> None:
    drifted = bundle_with_provenance(raster_hash="0" * 64)
    with pytest.raises(RuntimeError, match="provenance mismatch for training_raster"):
        predict_module._verify_provenance(drifted)


def test_a_bundle_without_provenance_is_served_but_cannot_be_checked(
    bundle_with_provenance,
) -> None:
    """It must not raise - the shipped model is one of these - and it must not
    be mistaken for a verified one, which is what active_provenance() reports."""
    predict_module._verify_provenance({"model": object(), "features": ["b11"]})


def test_the_served_bundle_reports_whether_it_is_bound(monkeypatch: pytest.MonkeyPatch) -> None:
    import src.models.prospectivity.explain as explain_module

    monkeypatch.setattr(predict_module, "active_model_path", lambda: Path("/nonexistent.pkl"))
    monkeypatch.setattr(explain_module, "load_bundle", lambda *_a, **_k: {"features": []})
    assert predict_module.active_provenance() is None

    monkeypatch.setattr(
        explain_module, "load_bundle", lambda *_a, **_k: {"provenance": {"training_seed": 42}}
    )
    assert predict_module.active_provenance() == {"training_seed": 42}


def test_an_unreadable_model_reports_unbound_rather_than_raising(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Health must answer even when the model cannot be loaded at all."""
    import src.models.prospectivity.explain as explain_module

    def explode(*_a: object, **_k: object) -> None:
        raise FileNotFoundError("no model")

    monkeypatch.setattr(explain_module, "load_bundle", explode)
    assert predict_module.active_provenance() is None


# --- the acceptance gate decides what may serve --------------------------


def _serving_features() -> list[str]:
    """Whatever the active model takes: a candidate that changes the feature
    space is rejected for that reason, which would mask the one under test."""
    from src.models.prospectivity import predict

    if predict.SHIPPED_MODEL_PATH.exists():
        return list(joblib.load(predict.SHIPPED_MODEL_PATH)["features"])
    return ["b11", "b12"]


FULL_PROVENANCE = {
    "schema": "prospectivity-provenance-v1",
    "training_raster": {"path": "/data/s2.tif", "sha256": "a" * 64},
    "encoder": {"path": "/models/autoencoder_v1.pt", "sha256": "b" * 64},
    "preprocessing": {"s2_scale": 10000},
    "training_seed": 42,
}


def _staged(store: Path, *, provenance: bool | dict, folds: list[dict]) -> Path:
    staged = registry.staging_dir("job-accept", 7)
    staged.mkdir(parents=True, exist_ok=True)
    bundle: dict = {"model": "m", "features": _serving_features(), "elkan_noto_c": 0.8}
    if provenance is True:
        bundle["provenance"] = dict(FULL_PROVENANCE)
    elif isinstance(provenance, dict):
        bundle["provenance"] = provenance
    joblib.dump(bundle, staged / registry.MODEL_FILENAME)
    (staged / registry.METRICS_FILENAME).write_text(
        json.dumps({"version": "candidate", "folds": folds}), encoding="utf-8"
    )
    return staged


@pytest.fixture()
def store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "registry"
    monkeypatch.setattr(registry, "REGISTRY_DIR", root)
    monkeypatch.setattr(registry, "VERSIONS_DIR", root / "versions")
    monkeypatch.setattr(registry, "STAGING_DIR", root / "staging")
    monkeypatch.setattr(registry, "POINTER_PATH", root / "active.json")
    monkeypatch.setattr(registry, "LOCK_PATH", root / ".registry.lock")
    registry.clear_pointer_cache()
    yield root
    registry.clear_pointer_cache()


GOOD_FOLDS = [{"auc": 0.71, "auc_pr": 0.24, "n_test": 100, "n_test_pos": 5}] * 3
#: AUC at chance, and AUC-PR no better than the 5% base rate.
CHANCE_FOLDS = [{"auc": 0.50, "auc_pr": 0.05, "n_test": 100, "n_test_pos": 5}] * 3


def test_a_candidate_with_no_recorded_inputs_is_not_accepted(store: Path) -> None:
    report = registry.acceptance_report(
        _staged(store, provenance=False, folds=GOOD_FOLDS), registry.active_model()
    )
    assert not report.accepted
    assert any("provenance" in reason for reason in report.reasons)


def test_a_candidate_no_better_than_chance_is_not_accepted(store: Path) -> None:
    report = registry.acceptance_report(
        _staged(store, provenance=True, folds=CHANCE_FOLDS), registry.active_model()
    )
    assert not report.accepted
    assert any("chance" in reason or "base rate" in reason for reason in report.reasons), report.reasons


def test_a_candidate_with_no_metrics_at_all_is_not_accepted(store: Path) -> None:
    report = registry.acceptance_report(
        _staged(store, provenance=True, folds=[]), registry.active_model()
    )
    assert not report.accepted
    assert any("no fold metrics" in reason for reason in report.reasons)


def test_a_rejected_candidate_is_kept_as_evidence_but_never_activated(store: Path) -> None:
    """Publishing is how the run is auditable; activation is what it serves."""
    staged = _staged(store, provenance=False, folds=CHANCE_FOLDS)
    published = registry.publish(
        staged=staged,
        job_id="job-accept",
        fence=7,
        activate=True,
        still_owns_job=lambda: True,
        acceptance_check=registry.acceptance_report,
    )
    assert published.acceptance is not None and not published.acceptance.accepted
    assert not published.activated, "a rejected candidate must not become live"
    # The artifact is still on disk, with its metrics, so the rejection can be
    # examined rather than taken on trust.
    assert published.path.is_file()
    assert (published.path.parent / registry.METRICS_FILENAME).is_file()
    # And the pointer never moved.
    assert registry.read_pointer() is None


def test_an_accepted_candidate_does_become_live(store: Path) -> None:
    published = registry.publish(
        staged=_staged(store, provenance=True, folds=GOOD_FOLDS),
        job_id="job-accept",
        fence=7,
        activate=True,
        still_owns_job=lambda: True,
        acceptance_check=registry.acceptance_report,
    )
    assert published.acceptance is not None and published.acceptance.accepted, published.acceptance.reasons
    assert published.activated
    assert registry.active_model().version == published.version
    # What the registry says is live is what inference resolves to.
    assert predict_module.active_model_path() == published.path


def test_an_empty_provenance_block_does_not_count_as_provenance(store: Path) -> None:
    """`provenance: {}` used to pass the gate by existing. It records nothing,
    so inference has nothing to compare against and drift goes undetected."""
    report = registry.acceptance_report(
        _staged(store, provenance={}, folds=GOOD_FOLDS), registry.active_model()
    )
    assert not report.accepted
    assert any("provenance" in reason for reason in report.reasons), report.reasons


def test_provenance_without_digests_does_not_count_either(store: Path) -> None:
    partial = {"schema": "prospectivity-provenance-v1", "training_seed": 42,
               "preprocessing": {"s2_scale": 10000},
               "training_raster": {"path": "/data/s2.tif"}, "encoder": {"path": "/m/ae.pt"}}
    report = registry.acceptance_report(
        _staged(store, provenance=partial, folds=GOOD_FOLDS), registry.active_model()
    )
    assert not report.accepted
    reasons = " ".join(report.reasons)
    assert "training_raster digest" in reasons and "encoder digest" in reasons, report.reasons


def test_provenance_missing_the_seed_or_preprocessing_is_rejected(store: Path) -> None:
    for dropped in ("training_seed", "preprocessing"):
        partial = {key: value for key, value in FULL_PROVENANCE.items() if key != dropped}
        report = registry.acceptance_report(
            _staged(store, provenance=partial, folds=GOOD_FOLDS), registry.active_model()
        )
        assert not report.accepted, dropped
        assert any(dropped in reason for reason in report.reasons), report.reasons


def test_exactly_chance_is_not_good_enough(store: Path) -> None:
    """The boundary, stated explicitly: AUC 0.500 is a coin flip, and lift 1.0
    is the base rate. `< MIN` let both through; `<= MIN` does not."""
    exact = [{"auc": 0.50, "auc_pr": 0.05, "n_test": 100, "n_test_pos": 5}] * 3
    report = registry.acceptance_report(
        _staged(store, provenance=True, folds=exact), registry.active_model()
    )
    assert not report.accepted
    reasons = " ".join(report.reasons)
    assert "not better than chance" in reasons and "does not beat the base rate" in reasons


def test_just_above_chance_is(store: Path) -> None:
    barely = [{"auc": 0.51, "auc_pr": 0.06, "n_test": 100, "n_test_pos": 5}] * 3
    report = registry.acceptance_report(
        _staged(store, provenance=True, folds=barely), registry.active_model()
    )
    assert report.accepted, report.reasons
