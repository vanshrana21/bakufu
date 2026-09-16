"""Shared pytest fixtures.

The DB-backed fixtures talk to the configured Supabase instance, so every test
that needs one is skipped when DATABASE_URL is unset.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

#: The API refuses to start without API_KEY, so pin a test key before anything
#: imports the settings. An environment variable outranks backend/.env, so the
#: suite never depends on - or sends - the real key.
TEST_API_KEY = "pytest-api-key"
os.environ["API_KEY"] = TEST_API_KEY

from src.config.settings import settings  # noqa: E402 - must follow the key above

requires_db = pytest.mark.skipif(
    not settings.DATABASE_URL, reason="DATABASE_URL not configured in .env"
)


@pytest.fixture(scope="session")
def db_session() -> Iterator[Session]:
    """Read-only session against the configured database."""
    if not settings.DATABASE_URL:
        pytest.skip("DATABASE_URL not configured in .env")

    from src.db.session import SessionLocal

    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(scope="session")
def api_headers() -> dict[str, str]:
    """What every request needs: the gate in src/api/security.py rejects the rest."""
    return {"X-API-Key": TEST_API_KEY}


@pytest.fixture(scope="session")
def api_client(api_headers: dict[str, str]) -> Iterator[TestClient]:
    """TestClient bound to the real app, carrying the API key."""
    from src.api.main import app

    with TestClient(app, headers=api_headers) as client:
        yield client


# --- Phase 2 fixtures ---------------------------------------------------


@pytest.fixture(scope="session")
def dummy_features() -> "pd.DataFrame":
    """A small synthetic frame with the full 78-column feature schema.

    Values are arbitrary but finite, so anything that merely needs correctly
    shaped input can use this without touching rasters or the database.
    """
    import numpy as np
    import pandas as pd

    from src.models.prospectivity.pu_xgboost import ALL_FEATURES

    rng = np.random.default_rng(0)
    return pd.DataFrame(
        rng.uniform(0.0, 1.0, size=(40, len(ALL_FEATURES))).astype("float64"),
        columns=ALL_FEATURES,
    )


@pytest.fixture(scope="session")
def trained_model_path(tmp_path_factory: pytest.TempPathFactory, dummy_features) -> "Path":
    """A real XGBoost bundle trained on synthetic data.

    Genuinely fitted rather than mocked, so SHAP and the prediction path
    exercise real model behaviour without depending on the Phase 2 training
    run having been executed.
    """
    import joblib
    import numpy as np
    from xgboost import XGBClassifier

    from src.models.prospectivity.pu_xgboost import ALL_FEATURES, XGB_PARAMS

    rng = np.random.default_rng(1)
    y = (dummy_features["b11"] + rng.normal(0, 0.05, len(dummy_features)) > 0.5).astype(int).to_numpy()
    if len(np.unique(y)) < 2:  # guard against a degenerate synthetic split
        y[:5] = 0
        y[5:10] = 1

    params = {**XGB_PARAMS, "n_estimators": 25, "max_depth": 3}
    model = XGBClassifier(**params)
    model.fit(dummy_features, y, sample_weight=np.full(len(y), 0.8))

    path = tmp_path_factory.mktemp("models") / "test_prospectivity.pkl"
    joblib.dump(
        {
            "model": model,
            "features": list(ALL_FEATURES),
            "elkan_noto_c": 0.8,
            "n_train": int(len(y)),
            "n_positive": int(y.sum()),
            "params": params,
        },
        path,
    )
    return path
