"""The model registry: publishing, fencing, promotion and what inference loads.

Training used to write straight onto a path inference reads, guarded by a lease
check and then a separate rename - two steps a stalled worker could be
interrupted between. Here the fence comparison, the ownership check and the
pointer write happen inside one lock, artifacts are immutable, and serving
follows the pointer rather than a constant captured at import.
"""

from __future__ import annotations

import json
from pathlib import Path

import joblib
import pytest

from src.models import registry


@pytest.fixture()
def store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A registry of its own, so nothing here touches models/."""
    root = tmp_path / "registry"
    monkeypatch.setattr(registry, "REGISTRY_DIR", root)
    monkeypatch.setattr(registry, "VERSIONS_DIR", root / "versions")
    monkeypatch.setattr(registry, "STAGING_DIR", root / "staging")
    monkeypatch.setattr(registry, "POINTER_PATH", root / "active.json")
    monkeypatch.setattr(registry, "LOCK_PATH", root / ".registry.lock")
    registry.clear_pointer_cache()
    yield root
    registry.clear_pointer_cache()


def _stage(job_id: str, fence: int, marker: str = "bundle") -> Path:
    """A staged artifact shaped like a real one."""
    staged = registry.staging_dir(job_id, fence)
    staged.mkdir(parents=True, exist_ok=True)
    joblib.dump(
        {"model": marker, "features": ["b11", "b12"], "elkan_noto_c": 0.8},
        staged / registry.MODEL_FILENAME,
    )
    (staged / registry.METRICS_FILENAME).write_text(
        json.dumps({"version": marker, "folds": []}), encoding="utf-8"
    )
    return staged


def _publish(job_id: str, fence: int, *, owns: bool = True, activate: bool = True, marker: str = "bundle"):
    return registry.publish(
        staged=_stage(job_id, fence, marker),
        job_id=job_id,
        fence=fence,
        activate=activate,
        still_owns_job=lambda: owns,
    )


# --- publishing ----------------------------------------------------------


def test_an_artifact_is_validated_before_it_is_published(store: Path) -> None:
    staged = registry.staging_dir("job", 1)
    staged.mkdir(parents=True)
    joblib.dump({"model": "no features here"}, staged / registry.MODEL_FILENAME)

    with pytest.raises(registry.RegistryError, match="missing features"):
        registry.publish(staged=staged, job_id="job", fence=1, activate=True, still_owns_job=lambda: True)
    assert registry.read_pointer() is None
    assert registry.versions() == []


def test_publishing_does_not_touch_the_previous_artifact(store: Path) -> None:
    first = _publish("job-one", 1, marker="first")
    second = _publish("job-two", 2, marker="second")

    assert first.version != second.version
    assert joblib.load(first.path)["model"] == "first", "the earlier version was modified"
    assert joblib.load(second.path)["model"] == "second"
    assert registry.active_model().version == second.version


# --- fencing: mandatory tests 2 and 3 ------------------------------------


def test_two_workers_on_one_job_cannot_both_publish(store: Path) -> None:
    """The first claim lost the job; only the newer claim may publish."""
    newer = _publish("same-job", 5, marker="newer")

    with pytest.raises(registry.StaleFence):
        _publish("same-job", 4, owns=False, marker="older")

    assert registry.active_model().version == newer.version
    assert joblib.load(registry.active_model().path)["model"] == "newer"


def test_a_stalled_worker_cannot_overwrite_a_newer_artifact(store: Path) -> None:
    """Stage first, lose the job, then try to publish: the fence refuses it."""
    stale_staged = _stage("stalled-job", 3, marker="stale")
    newer = _publish("newer-job", 7, marker="newer")

    # It still believes it owns the job - the check the old code relied on.
    with pytest.raises(registry.StaleFence, match="not newer"):
        registry.publish(
            staged=stale_staged, job_id="stalled-job", fence=3, activate=True, still_owns_job=lambda: True
        )

    assert registry.active_model().version == newer.version
    assert joblib.load(registry.active_model().path)["model"] == "newer"
    assert registry.read_pointer()["fence"] == 7


def test_losing_the_job_stops_a_publish_even_with_a_newer_fence(store: Path) -> None:
    first = _publish("job-one", 1, marker="first")

    with pytest.raises(registry.StaleFence, match="no longer owned"):
        _publish("job-two", 9, owns=False, marker="taken-over")

    assert registry.active_model().version == first.version
    assert joblib.load(registry.active_model().path)["model"] == "first"


def test_a_crash_between_staging_and_publishing_changes_nothing(store: Path) -> None:
    """Mandatory 4: staged work that never published leaves serving alone."""
    published = _publish("job-one", 1, marker="first")
    _stage("job-two", 2, marker="never-published")  # the worker dies here

    assert registry.active_model().version == published.version
    assert joblib.load(registry.active_model().path)["model"] == "first"
    assert registry.versions() == [published.version]


def test_publishing_the_same_version_twice_is_idempotent(store: Path) -> None:
    first = _publish("job-one", 1, marker="first")
    again = registry.publish(
        staged=_stage("job-one", 1, marker="rewritten"),
        job_id="job-one",
        fence=1,
        activate=False,
        still_owns_job=lambda: True,
    )
    assert again.version == first.version
    # Versions are immutable: the second attempt did not rewrite the artifact.
    assert joblib.load(first.path)["model"] == "first"


# --- what inference loads: mandatory tests 6 and 7 -----------------------


def test_serving_follows_the_pointer(store: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from src.models.prospectivity import predict

    monkeypatch.delenv("PROSPECTIVITY_MODEL", raising=False)
    assert predict.active_model_path() == predict.SHIPPED_MODEL_PATH

    published = _publish("job-one", 1, marker="trained")
    assert predict.active_model_path() == published.path
    assert predict.active_model_version() == published.version


def test_the_env_override_still_wins(store: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _publish("job-one", 1)
    monkeypatch.setenv("PROSPECTIVITY_MODEL", "/tmp/some-other.pkl")
    assert registry.active_model().source == "env"
    assert registry.active_model().path == Path("/tmp/some-other.pkl")


def test_a_promotion_reloads_the_bundle_rather_than_serving_the_cached_one(
    store: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Mandatory 7: the path-keyed cache used to pin the first model forever."""
    from src.models.prospectivity import explain, predict

    monkeypatch.delenv("PROSPECTIVITY_MODEL", raising=False)
    explain.clear_bundle_cache()

    first = _publish("job-one", 1, marker="first")
    assert explain.load_bundle(predict.active_model_path())["model"] == "first"

    second = _publish("job-two", 2, marker="second")
    assert second.version != first.version
    assert explain.load_bundle(predict.active_model_path())["model"] == "second"

    # Even at one unchanged path, a replaced file is a different bundle.
    same_path = store / "fixed.pkl"
    joblib.dump({"model": "a", "features": ["x"], "elkan_noto_c": 0.5}, same_path)
    assert explain.load_bundle(same_path)["model"] == "a"
    joblib.dump({"model": "b", "features": ["x"], "elkan_noto_c": 0.5}, same_path)
    assert explain.load_bundle(same_path)["model"] == "b"


def test_the_heatmap_cache_key_moves_with_the_active_version(
    store: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Otherwise a promotion would keep serving tiles scored by the old model."""
    from src.api.routers import reference
    from src.models.prospectivity import predict

    monkeypatch.delenv("PROSPECTIVITY_MODEL", raising=False)
    bbox = (79.0, 21.3, 80.6, 22.1)
    before = reference._cache_key(bbox, 32, "none", predict.active_model_version())
    _publish("job-one", 1)
    after = reference._cache_key(bbox, 32, "none", predict.active_model_version())
    assert before != after


# --- metrics travel with the model: mandatory test 8 ---------------------


def test_metrics_are_published_with_the_model(store: Path) -> None:
    published = _publish("job-one", 1, marker="first")
    version_files = {path.name for path in published.path.parent.iterdir()}
    assert version_files == {
        registry.MODEL_FILENAME,
        registry.METRICS_FILENAME,
        registry.MANIFEST_FILENAME,
    }
    manifest = json.loads((published.path.parent / registry.MANIFEST_FILENAME).read_text())
    assert manifest["job_id"] == "job-one" and manifest["fence"] == 1
    assert manifest["version"] == published.version
    assert manifest["sha256"] == registry.sha256(published.path)


# --- manual promotion ----------------------------------------------------


def test_promoting_by_hand_moves_the_pointer_and_never_goes_backwards(store: Path) -> None:
    first = _publish("job-one", 1, activate=True, marker="first")
    second = _publish("job-two", 2, activate=False, marker="second")
    assert registry.active_model().version == first.version

    registry.activate_version(second.version)
    assert registry.active_model().version == second.version

    # A rollback is allowed, but it takes a fence above the one it replaces, so
    # a worker still holding the older fence cannot undo it.
    rolled_back = registry.activate_version(first.version)
    assert rolled_back.version == first.version
    assert rolled_back.fence > 2
    with pytest.raises(registry.StaleFence):
        _publish("job-three", 2, marker="stale")


def test_an_unreadable_pointer_falls_back_to_the_shipped_model(store: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from src.models.prospectivity.predict import SHIPPED_MODEL_PATH

    monkeypatch.delenv("PROSPECTIVITY_MODEL", raising=False)
    _publish("job-one", 1)
    registry.POINTER_PATH.write_text("{ this is not json", encoding="utf-8")
    registry.clear_pointer_cache()

    active = registry.active_model()
    assert active.source == "shipped" and active.path == SHIPPED_MODEL_PATH


def test_a_pointer_to_a_missing_version_falls_back(store: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import shutil

    monkeypatch.delenv("PROSPECTIVITY_MODEL", raising=False)
    published = _publish("job-one", 1)
    shutil.rmtree(published.path.parent)
    registry.clear_pointer_cache()
    assert registry.active_model().source == "shipped"


# --- the database, the registry and the pointer must agree ---------------


def test_reconcile_is_quiet_when_everything_matches(store: Path) -> None:
    published = _publish("job-one", 1, marker="first")
    digest = registry.sha256(published.path)
    assert registry.reconcile([(published.version, digest)]) == []


def test_reconcile_reports_a_version_the_database_names_but_the_registry_lost(store: Path) -> None:
    import shutil

    published = _publish("job-one", 1)
    digest = registry.sha256(published.path)
    shutil.rmtree(published.path.parent)
    registry.clear_pointer_cache()

    problems = registry.reconcile([(published.version, digest)])
    assert any("missing from the registry" in problem for problem in problems)
    assert any("active pointer names a version that is not" in problem for problem in problems)


def test_reconcile_reports_an_artifact_that_changed_under_the_database(store: Path) -> None:
    published = _publish("job-one", 1, marker="first")
    digest = registry.sha256(published.path)
    joblib.dump({"model": "swapped", "features": ["b11"], "elkan_noto_c": 0.8}, published.path)

    problems = registry.reconcile([(published.version, digest)])
    assert any("no longer matches its recorded digest" in problem for problem in problems)


def test_reconcile_reports_an_unreadable_pointer(store: Path) -> None:
    _publish("job-one", 1)
    registry.POINTER_PATH.write_text("{ not json", encoding="utf-8")
    registry.clear_pointer_cache()

    assert any("unreadable" in problem for problem in registry.reconcile([]))


def test_health_reports_a_degraded_registry(store: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Fail-soft serving is fine; staying quiet about it is not."""
    from fastapi.testclient import TestClient

    from src.api.main import app
    from src.api.security import API_KEY_HEADER
    from src.config.settings import get_server_settings

    monkeypatch.delenv("PROSPECTIVITY_MODEL", raising=False)
    key = get_server_settings().API_KEY
    assert key is not None
    headers = {API_KEY_HEADER: key.get_secret_value()}
    client = TestClient(app, headers=headers)

    app.state.registry_problems = []
    healthy = client.get("/").json()
    assert healthy["status"] == "ok" and healthy["degraded"] == []
    assert healthy["model_source"] == "shipped"

    app.state.registry_problems = ["job-one-00000001: recorded in the database, missing from the registry"]
    degraded = client.get("/").json()
    assert degraded["status"] == "degraded"
    assert degraded["degraded"] == app.state.registry_problems
    app.state.registry_problems = []


def test_a_published_job_is_found_again_after_a_crash(store: Path) -> None:
    """Mandatory 5 at the registry level: the artifact identifies its job."""
    published = _publish("job-one", 1)
    assert registry.artifact_for_job("job-one") == published.version
    assert registry.artifact_for_job("never-ran") is None
