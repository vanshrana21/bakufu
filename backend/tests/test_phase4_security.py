"""Regression tests for Phase 4 artifact and archive trust boundaries."""

from __future__ import annotations

import zipfile
from pathlib import Path

import joblib
import pytest

from src.data.ingest.load_ngdr_bundle import _extract_bundle
from src.models import registry
from src.models.artifact_security import UntrustedArtifactError


def test_ngdr_extraction_rejects_parent_traversal(tmp_path: Path) -> None:
    archive_path = tmp_path / "bundle.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("../outside.geojson", "{}")

    with pytest.raises(ValueError, match="escapes extraction directory"):
        _extract_bundle(archive_path, tmp_path / "extract")
    assert not (tmp_path / "outside.geojson").exists()


def test_ngdr_extraction_rejects_absolute_member(tmp_path: Path) -> None:
    archive_path = tmp_path / "bundle.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("/outside.geojson", "{}")

    with pytest.raises(ValueError, match="escapes extraction directory"):
        _extract_bundle(archive_path, tmp_path / "extract")


def test_production_load_rejects_untrusted_joblib(tmp_path: Path) -> None:
    path = tmp_path / "untrusted.pkl"
    joblib.dump({"model": "attacker"}, path)

    from src.models.prospectivity import explain

    with pytest.raises(UntrustedArtifactError, match="outside a trusted"):
        explain.load_bundle(path)


def test_production_load_rejects_tampered_registry_artifact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "registry"
    monkeypatch.setattr(registry, "REGISTRY_DIR", root)
    monkeypatch.setattr(registry, "VERSIONS_DIR", root / "versions")
    monkeypatch.setattr(registry, "STAGING_DIR", root / "staging")
    monkeypatch.setattr(registry, "POINTER_PATH", root / "active.json")
    monkeypatch.setattr(registry, "LOCK_PATH", root / ".registry.lock")
    registry.clear_pointer_cache()

    staged = registry.staging_dir("security-job", 1)
    staged.mkdir(parents=True)
    joblib.dump({"model": "safe", "features": ["x"], "elkan_noto_c": 0.5}, staged / "model.pkl")
    published = registry.publish(
        staged=staged,
        job_id="security-job",
        fence=1,
        activate=True,
        still_owns_job=lambda: True,
    )
    published.path.write_bytes(b"tampered")

    from src.models.prospectivity import explain

    with pytest.raises(UntrustedArtifactError, match="digest mismatch"):
        explain.load_bundle(published.path)
