"""Every artifact the API deserialises has to be one this build expects.

A model bundle and an encoder checkpoint are both pickles executed inside the
API process. They are pinned by digest, loaded only from trusted directories,
and the encoder is loaded weights-only so a swapped file cannot run code even
if it reached the loader.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.models import artifact_security
from src.models.artifact_security import (
    SHIPPED_DIGESTS,
    UntrustedArtifactError,
    fingerprint,
    load_torch_checkpoint,
    verify_model_path,
)
from src.models.prospectivity.autoencoder import MODEL_PATH as ENCODER_PATH
from src.models.prospectivity.autoencoder import encoder_fingerprint, load_autoencoder


def test_the_encoder_is_pinned_like_the_models() -> None:
    """It defines the 64 dimensions every bundle was trained against."""
    assert ENCODER_PATH.name in SHIPPED_DIGESTS


@pytest.mark.skipif(not ENCODER_PATH.exists(), reason="encoder artifact not present")
def test_the_shipped_encoder_matches_its_pinned_digest() -> None:
    verify_model_path(ENCODER_PATH)
    assert artifact_security.digest(ENCODER_PATH) == SHIPPED_DIGESTS[ENCODER_PATH.name]


@pytest.mark.skipif(not ENCODER_PATH.exists(), reason="encoder artifact not present")
def test_a_swapped_encoder_is_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The failure this exists for: a checkpoint replaced under the API."""
    import shutil

    models = tmp_path / "models"
    models.mkdir()
    swapped = models / ENCODER_PATH.name
    shutil.copy(ENCODER_PATH, swapped)
    swapped.write_bytes(swapped.read_bytes() + b"tampered")
    monkeypatch.setattr(artifact_security.settings, "MODELS_DIR", models)

    with pytest.raises(UntrustedArtifactError, match="digest mismatch"):
        verify_model_path(swapped)
    with pytest.raises(UntrustedArtifactError):
        load_torch_checkpoint(swapped)


def test_an_artifact_outside_the_trusted_directories_is_refused(tmp_path: Path) -> None:
    stray = tmp_path / "somewhere-else.pt"
    stray.write_bytes(b"not a model")
    with pytest.raises(UntrustedArtifactError, match="outside a trusted model directory"):
        verify_model_path(stray)


@pytest.mark.skipif(not ENCODER_PATH.exists(), reason="encoder artifact not present")
def test_the_encoder_loads_weights_only(monkeypatch: pytest.MonkeyPatch) -> None:
    """Loading must not be able to execute code from the checkpoint."""
    import torch

    seen: list[dict[str, object]] = []
    real_load = torch.load

    def spy(path, **kwargs):
        seen.append(kwargs)
        return real_load(path, **kwargs)

    monkeypatch.setattr(torch, "load", spy)
    model = load_autoencoder(ENCODER_PATH)

    assert model is not None
    assert seen and all(call.get("weights_only") is True for call in seen)


@pytest.mark.skipif(not ENCODER_PATH.exists(), reason="encoder artifact not present")
def test_the_encoder_fingerprint_changes_with_the_file(tmp_path: Path) -> None:
    """Cache keys ride on this, so it has to move when the encoder does."""
    first = tmp_path / "a.pt"
    first.write_bytes(b"one")
    second = tmp_path / "b.pt"
    second.write_bytes(b"two")

    assert fingerprint(first) != fingerprint(second)
    assert fingerprint(first) == fingerprint(first)
    assert encoder_fingerprint() == fingerprint(ENCODER_PATH)


def test_a_missing_encoder_reports_rather_than_raises() -> None:
    assert encoder_fingerprint(Path("/nonexistent/encoder.pt")) == "missing"


@pytest.mark.skipif(not ENCODER_PATH.exists(), reason="encoder artifact not present")
def test_cached_tiles_do_not_survive_an_encoder_change(monkeypatch: pytest.MonkeyPatch) -> None:
    """A swapped encoder changes what a score means, so it changes the key."""
    from src.api.routers import reference
    from src.models.prospectivity import autoencoder, predict

    bbox = (79.0, 21.3, 80.6, 22.1)
    version = f"{predict.active_model_version()}+ae{autoencoder.encoder_fingerprint()}"
    before = reference._cache_key(bbox, 32, "none", version)
    after = reference._cache_key(bbox, 32, "none", f"{predict.active_model_version()}+aedeadbeef1234")
    assert before != after
