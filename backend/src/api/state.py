"""Artifacts loaded once at API startup and held in `app.state`.

Loading is eager and happens in the lifespan handler, not lazily per request:
a missing model should be visible the moment the process starts, and the
first request should not pay a multi-second model load. Prophet in particular
takes 1-2 seconds to unpickle.

A load failure does not stop the API. Each artifact records its own error, and
the endpoints that need it return 500 `model_not_loaded` naming the file, so a
missing shortfall model cannot take down the production-history endpoint.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.config.settings import settings

logger = logging.getLogger("api.state")

#: Promoted artifacts. Training writes elsewhere; promotion is a manual copy.
#: A training run once overwrote the served forecast model and the API
#: silently served a rejected variant while returning 200 - hence the split.
SHIPPED_FORECAST_MODEL: Path = settings.MODELS_DIR / "prophet_baseline_v1_0_shipped.pkl"
SHIPPED_FORECAST_METRICS: Path = settings.DATA_PROCESSED / "prophet_metrics_baseline_v1_0.json"
SHIPPED_BACKTEST_ROWS: Path = settings.DATA_PROCESSED / "prophet_backtest_rows_baseline_v1_0.parquet"
SHIPPED_SHORTFALL_MODEL: Path = settings.MODELS_DIR / "shortfall_classifier_v1.pkl"

#: The bundles carry no version string of their own - only `variant` and
#: `regressors` - so the value the API reports is declared here rather than
#: derived from a filename. Bump it when a different artifact is promoted.
FORECAST_MODEL_VERSION = "prophet_baseline_v1.0"
SHORTFALL_MODEL_VERSION = "shortfall_classifier_v1"

PRODUCTION_SERIES: Path = settings.DATA_PROCESSED / "msmp_mn_monthly_wide.parquet"
SHORTFALL_FEATURES: Path = settings.DATA_PROCESSED / "shortfall_features.parquet"


@dataclass
class Artifact:
    """One loaded artifact plus how its load went."""

    name: str
    path: Path
    value: Any = None
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None and self.value is not None


@dataclass
class AppState:
    artifacts: dict[str, Artifact] = field(default_factory=dict)

    def get(self, name: str) -> Artifact:
        return self.artifacts.get(name, Artifact(name=name, path=Path(name), error="not loaded"))

    def require(self, name: str) -> Any:
        """Return the loaded value or raise the API's 500 for a missing model."""
        from src.api.errors import ModelNotLoaded

        artifact = self.get(name)
        if not artifact.ok:
            raise ModelNotLoaded(artifact.path.name, artifact.error or "not loaded")
        return artifact.value

    @property
    def degraded(self) -> list[str]:
        return sorted(name for name, a in self.artifacts.items() if not a.ok)


def _load(state: AppState, name: str, path: Path, loader) -> None:
    artifact = Artifact(name=name, path=path)
    try:
        if not path.exists():
            raise FileNotFoundError(f"{path.name} not found in {path.parent}")
        artifact.value = loader(path)
    except Exception as exc:  # noqa: BLE001 - recorded, surfaced per endpoint
        artifact.error = f"{type(exc).__name__}: {exc}"
        logger.warning("artifact %s failed to load: %s", name, artifact.error)
    else:
        logger.info("artifact %s loaded from %s", name, path.name)
    state.artifacts[name] = artifact


def load_all() -> AppState:
    """Load every served artifact. Never raises; failures are recorded."""
    import joblib
    import pandas as pd

    state = AppState()
    _load(state, "forecast_model", SHIPPED_FORECAST_MODEL, joblib.load)
    _load(state, "forecast_metrics", SHIPPED_FORECAST_METRICS, lambda p: pd.read_json(p))
    _load(state, "backtest_rows", SHIPPED_BACKTEST_ROWS, pd.read_parquet)
    _load(state, "shortfall_model", SHIPPED_SHORTFALL_MODEL, joblib.load)
    _load(state, "production_series", PRODUCTION_SERIES, pd.read_parquet)
    _load(state, "shortfall_features", SHORTFALL_FEATURES, pd.read_parquet)
    return state
