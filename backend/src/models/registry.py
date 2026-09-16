"""Versioned model artifacts and the pointer that decides which one is served.

A training run never writes over the served model. It trains into a staging
directory of its own, the artifact is validated, and only then is it moved -
whole, by rename - into `models/registry/versions/<version>/`. Versions are
immutable once published.

Which version inference uses is a separate decision, recorded in
`models/registry/active.json`. Promotion stays deliberate: the same discipline
src/models/prospectivity/predict.py documents after a training run silently
replaced a shipped forecast model. A job activates its own artifact only when
the server is configured to (TRAINING_ACTIVATE_ON_SUCCESS); otherwise the
artifact waits for `python -m scripts.promote_model <version>`.

Publishing is fenced. Every claim of a training job takes a fence from the
database that is strictly greater than every fence handed out before it, and a
publish must present a fence greater than the one in the pointer AND still own
its job. Both checks and the pointer write happen inside one lock, so a worker
that stalled and lost its job cannot wake up and overwrite a newer artifact.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import logging
import os
import shutil
import threading
from collections.abc import Callable, Iterable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from src.config.settings import settings

logger = logging.getLogger("models.registry")

REGISTRY_DIR: Path = settings.MODELS_DIR / "registry"
VERSIONS_DIR: Path = REGISTRY_DIR / "versions"
STAGING_DIR: Path = REGISTRY_DIR / "staging"
POINTER_PATH: Path = REGISTRY_DIR / "active.json"
LOCK_PATH: Path = REGISTRY_DIR / ".registry.lock"

MODEL_FILENAME = "model.pkl"
METRICS_FILENAME = "metrics.json"
MANIFEST_FILENAME = "manifest.json"

#: Keys a bundle must carry before it is allowed into the registry. An artifact
#: that cannot be loaded, or that is missing any of these, is rejected at
#: publish time rather than at the first request that needs it.
REQUIRED_BUNDLE_KEYS = ("model", "features", "elkan_noto_c")


class RegistryError(RuntimeError):
    """A publish or activation that must not proceed."""


class StaleFence(RegistryError):
    """The caller's fence is not newer than the active one: it lost its turn."""


@dataclass(frozen=True)
class ActiveModel:
    """The bundle inference should score with."""

    version: str
    path: Path
    fence: int
    #: "registry" once a version has been activated, "env" for the
    #: PROSPECTIVITY_MODEL override, "shipped" for the promoted default.
    source: Literal["registry", "env", "shipped"]


@dataclass(frozen=True)
class PublishedVersion:
    version: str
    path: Path
    fence: int
    job_id: str
    activated: bool


def version_id(job_id: str, fence: int) -> str:
    """One version per claim, so a retry after a takeover cannot reuse a directory."""
    return f"{job_id}-{fence:08d}"


def version_dir(version: str) -> Path:
    return VERSIONS_DIR / version


def staging_dir(job_id: str, fence: int) -> Path:
    """A private directory for one attempt. Removed whether it publishes or not."""
    return STAGING_DIR / version_id(job_id, fence)


# --- the lock -------------------------------------------------------------

_LOCAL_LOCK = threading.Lock()


@contextmanager
def registry_lock() -> Iterator[None]:
    """Exclude other threads and other processes on this host.

    A publish from another host is excluded by the caller's database advisory
    lock; this one covers the file moves and the pointer write.
    """
    REGISTRY_DIR.mkdir(parents=True, exist_ok=True)
    with _LOCAL_LOCK:
        with LOCK_PATH.open("a+") as handle:
            fcntl.flock(handle, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle, fcntl.LOCK_UN)


# --- reading the pointer --------------------------------------------------

_POINTER_CACHE: dict[str, Any] = {"stat": None, "pointer": None}
_POINTER_CACHE_LOCK = threading.Lock()


def _pointer_stat() -> tuple[int, int] | None:
    try:
        stat = POINTER_PATH.stat()
    except OSError:
        return None
    return (stat.st_mtime_ns, stat.st_size)


def read_pointer() -> dict[str, Any] | None:
    """The active.json contents, re-read whenever the file changes."""
    stat = _pointer_stat()
    with _POINTER_CACHE_LOCK:
        if stat is not None and stat == _POINTER_CACHE["stat"]:
            return _POINTER_CACHE["pointer"]
    pointer: dict[str, Any] | None = None
    if stat is not None:
        try:
            pointer = json.loads(POINTER_PATH.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            # A pointer we cannot read must not silently downgrade what is
            # served: say so, and fall back to the shipped model.
            logger.error("registry pointer %s is unreadable; serving the shipped model", POINTER_PATH)
            pointer = None
    with _POINTER_CACHE_LOCK:
        _POINTER_CACHE["stat"] = stat
        _POINTER_CACHE["pointer"] = pointer
    return pointer


def active_fence() -> int:
    pointer = read_pointer()
    return int(pointer["fence"]) if pointer else 0


def active_model() -> ActiveModel:
    """The model inference must load right now.

    PROSPECTIVITY_MODEL still wins, so a bundle can be exercised through a
    running API without touching the registry.
    """
    override = os.environ.get("PROSPECTIVITY_MODEL")
    if override:
        path = Path(override)
        return ActiveModel(version=path.stem, path=path, fence=0, source="env")

    pointer = read_pointer()
    if pointer is not None:
        path = version_dir(pointer["version"]) / pointer.get("model", MODEL_FILENAME)
        if path.exists():
            return ActiveModel(
                version=str(pointer["version"]), path=path, fence=int(pointer["fence"]), source="registry"
            )
        logger.error("active version %s is missing at %s; serving the shipped model", pointer["version"], path)

    from src.models.prospectivity.predict import SHIPPED_MODEL_PATH

    return ActiveModel(version=SHIPPED_MODEL_PATH.stem, path=SHIPPED_MODEL_PATH, fence=0, source="shipped")


# --- publishing -----------------------------------------------------------


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def validate_artifact(model_file: Path) -> dict[str, Any]:
    """Load the staged bundle and check it is the shape inference expects."""
    if not model_file.exists():
        raise RegistryError(f"training produced no model at {model_file}")
    import joblib

    try:
        bundle = joblib.load(model_file)
    except Exception as exc:  # noqa: BLE001 - any unpickling failure is a rejection
        raise RegistryError(f"staged bundle at {model_file} could not be loaded: {exc}") from exc
    if not isinstance(bundle, dict):
        raise RegistryError(f"staged bundle at {model_file} is {type(bundle).__name__}, not a dict")
    missing = [key for key in REQUIRED_BUNDLE_KEYS if key not in bundle]
    if missing:
        raise RegistryError(f"staged bundle at {model_file} is missing {', '.join(missing)}")
    features = bundle["features"]
    if not isinstance(features, (list, tuple)) or not features:
        raise RegistryError(f"staged bundle at {model_file} carries no feature list")
    return {"n_features": len(features), "features": list(features)[:5], "bytes": model_file.stat().st_size}


def artifact_for_job(job_id: str) -> str | None:
    """The version this job already published, if it did. Makes a retry a no-op."""
    if not VERSIONS_DIR.exists():
        return None
    for candidate in sorted(VERSIONS_DIR.iterdir(), reverse=True):
        manifest = candidate / MANIFEST_FILENAME
        if not manifest.is_file():
            continue
        try:
            if json.loads(manifest.read_text(encoding="utf-8")).get("job_id") == job_id:
                return candidate.name
        except (OSError, ValueError):
            continue
    return None


def _write_pointer(version: str, fence: int, job_id: str) -> None:
    """Replace active.json in one step; a reader sees the old or the new file."""
    pointer = {
        "version": version,
        "fence": fence,
        "job_id": job_id,
        "model": MODEL_FILENAME,
        "activated_at": datetime.now(UTC).isoformat(timespec="seconds"),
    }
    temporary = POINTER_PATH.with_name(f".active.{os.getpid()}.json")
    temporary.write_text(json.dumps(pointer, indent=2), encoding="utf-8")
    os.replace(temporary, POINTER_PATH)
    with _POINTER_CACHE_LOCK:  # the next read must not serve the previous file
        _POINTER_CACHE["stat"] = None
        _POINTER_CACHE["pointer"] = None


def publish(
    *,
    staged: Path,
    job_id: str,
    fence: int,
    activate: bool,
    still_owns_job: Callable[[], bool],
) -> PublishedVersion:
    """Move a staged artifact into the registry, optionally activating it.

    Everything that decides whether this publish may happen - the fence
    comparison and the ownership check - runs inside the registry lock,
    together with the move and the pointer write. A worker that stalls before
    this call and loses its job cannot get past `still_owns_job`; one that
    stalls after another version was activated cannot get past the fence.
    """
    version = version_id(job_id, fence)
    model_file = staged / MODEL_FILENAME
    facts = validate_artifact(model_file)

    with registry_lock():
        current = read_pointer()
        # A redelivery of the run that already published this exact version:
        # nothing to decide, and nothing to overwrite. Checking the fence here
        # would refuse a job its own artifact.
        already_active = current is not None and current["version"] == version
        if not already_active:
            if current is not None and fence <= int(current["fence"]):
                raise StaleFence(
                    f"fence {fence} is not newer than the active fence {current['fence']} "
                    f"(version {current['version']}); this run has been superseded"
                )
            if not still_owns_job():
                raise StaleFence(
                    f"job {job_id} is no longer owned by this worker; not publishing {version}"
                )

        target = version_dir(version)
        if target.exists():
            # The same claim already published: leave the immutable copy alone.
            logger.info("version %s is already in the registry", version)
            shutil.rmtree(staged, ignore_errors=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            (staged / MANIFEST_FILENAME).write_text(
                json.dumps(
                    {
                        "version": version,
                        "job_id": job_id,
                        "fence": fence,
                        "created_at": datetime.now(UTC).isoformat(timespec="seconds"),
                        "sha256": sha256(model_file),
                        **facts,
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
            os.replace(staged, target)  # atomic within the registry directory

        if activate and not already_active:
            _write_pointer(version, fence, job_id)
    return PublishedVersion(
        version=version,
        path=version_dir(version) / MODEL_FILENAME,
        fence=fence,
        job_id=job_id,
        activated=activate or already_active,
    )


def activate_version(version: str) -> ActiveModel:
    """Promote an existing version by hand. Refuses to go backwards."""
    target = version_dir(version)
    manifest_file = target / MANIFEST_FILENAME
    if not manifest_file.is_file():
        raise RegistryError(f"no version {version} in {VERSIONS_DIR}")
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    validate_artifact(target / MODEL_FILENAME)

    with registry_lock():
        current = read_pointer()
        fence = int(manifest["fence"])
        if current is not None and fence <= int(current["fence"]):
            # A hand promotion of an older artifact is a rollback, and needs a
            # fence of its own so no stale worker can undo it later.
            fence = int(current["fence"]) + 1
        _write_pointer(version, fence, str(manifest.get("job_id", "")))
    return active_model()


def reconcile(recorded: Iterable[tuple[str, str | None]]) -> list[str]:
    """Compare what the database says was published with what is on disk.

    Three sources have to agree: the job rows that name an artifact, the version
    directories, and the active pointer. Divergence is reported rather than
    repaired - deleting or rewriting a model artifact is never something this
    should decide on its own - and the API surfaces it on the health endpoint.
    """
    problems: list[str] = []
    for version, digest in recorded:
        model_file = version_dir(version) / MODEL_FILENAME
        if not model_file.is_file():
            problems.append(f"{version}: recorded in the database, missing from the registry")
        elif digest and sha256(model_file) != digest:
            problems.append(f"{version}: the artifact on disk no longer matches its recorded digest")

    pointer = read_pointer()
    if pointer is None and POINTER_PATH.exists():
        problems.append(f"{POINTER_PATH.name}: unreadable, so the shipped model is being served")
    elif pointer is not None:
        active_file = version_dir(pointer["version"]) / pointer.get("model", MODEL_FILENAME)
        if not active_file.is_file():
            problems.append(
                f"{pointer['version']}: the active pointer names a version that is not in the registry"
            )
    return problems


def versions() -> list[str]:
    if not VERSIONS_DIR.exists():
        return []
    return sorted(entry.name for entry in VERSIONS_DIR.iterdir() if (entry / MANIFEST_FILENAME).is_file())


def clear_pointer_cache() -> None:
    """Forget the cached pointer. Used at startup and by the tests."""
    with _POINTER_CACHE_LOCK:
        _POINTER_CACHE["stat"] = None
        _POINTER_CACHE["pointer"] = None
