"""Trust and integrity checks for model artifacts loaded by production code."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import joblib
from cachetools import LRUCache

from src.config.settings import settings

SHIPPED_DIGESTS: dict[str, str] = {
    "prospectivity_v6.pkl": "267c2de36697b18b4618e33ee6b1caed39e7c0a3a7f5d039bf5540de270c7c1f",
    "prophet_baseline_v1_0_shipped.pkl": "f4b04db998c5e94111781c2f18b5f3d4fb5923c43c3a1200b940c552b21407fd",
    "shortfall_classifier_v1.pkl": "b3f4997bc97612d1a266ef9383afc2d74eff22e9fd56c4f6afc2918e55e97fce",
    # The encoder defines the 64 dimensions every bundle was trained against, so
    # it is pinned like the models that consume it.
    "autoencoder_v1.pt": "24c39a1c97f150b1e2e6d80cf69d65c5a75f1351a6bfe44643998d7b832bb9ff",
}


class UntrustedArtifactError(RuntimeError):
    """A model is outside an approved trust boundary or has changed."""


def digest(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(block)
    return hasher.hexdigest()


def _inside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def verify_model_path(
    path: Path,
    *,
    registry_root: Path | None = None,
    allow_staging: bool = False,
) -> None:
    """Verify a production model before handing it to a pickle loader.

    Shipped artifacts are pinned to digests in source. Registry artifacts must
    carry an adjacent manifest whose digest matches the file. Staging is only
    allowed for the registry's own pre-publish shape validation.
    """
    path = path.resolve()
    if not path.is_file():
        raise UntrustedArtifactError(f"model artifact is missing: {path}")

    shipped_root = settings.MODELS_DIR.resolve()
    if _inside(path, shipped_root) and path.name in SHIPPED_DIGESTS:
        expected = SHIPPED_DIGESTS[path.name]
        actual = digest(path)
        if actual != expected:
            raise UntrustedArtifactError(
                f"shipped model digest mismatch for {path.name}: expected {expected}, got {actual}"
            )
        return

    root = (registry_root or settings.MODELS_DIR / "registry" / "versions").resolve()
    if _inside(path, root):
        manifest_path = path.parent / "manifest.json"
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            expected = manifest["sha256"]
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise UntrustedArtifactError(f"registry model has no valid digest manifest: {path}") from exc
        actual = digest(path)
        if not isinstance(expected, str) or actual != expected:
            raise UntrustedArtifactError(f"registry model digest mismatch: {path}")
        return

    staging_root = (root.parent / "staging") if root.name == "versions" else (
        settings.MODELS_DIR / "registry" / "staging"
    )
    if allow_staging and _inside(path, staging_root):
        return
    raise UntrustedArtifactError(f"model artifact is outside a trusted model directory: {path}")


def load_joblib(path: Path, **kwargs: Any) -> Any:
    """Verify and then load a trusted production joblib artifact."""
    verify_model_path(path, **kwargs)
    return joblib.load(path)


def load_torch_checkpoint(path: Path, **kwargs: Any) -> Any:
    """Verify and then load a trusted PyTorch checkpoint.

    Two locks, not one. The digest check says the file is the artifact this
    build expects, and weights_only=True keeps the loader to tensors and plain
    data, so a swapped checkpoint cannot execute code inside the API process
    even if it somehow passed the first check.
    """
    import torch

    verify_model_path(path, **kwargs)
    return torch.load(path, map_location="cpu", weights_only=True)


def fingerprint(path: Path) -> str:
    """A short digest for cache keys and health output, by path and mtime."""
    key = (str(path.resolve()), path.stat().st_mtime_ns)
    cached = _FINGERPRINTS.get(key)
    if cached is None:
        cached = _FINGERPRINTS[key] = digest(path)[:12]
    return cached


#: Bounded: one entry per artifact version this process has seen.
_FINGERPRINTS: LRUCache[tuple[str, int], str] = LRUCache(maxsize=16)
