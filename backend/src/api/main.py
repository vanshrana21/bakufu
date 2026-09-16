"""FastAPI application entry point."""

from __future__ import annotations

import logging
import threading
import time
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import SQLAlchemyError

from src.api.errors import ApiError, api_error_handler
from src.api.routers import (
    boreholes, dashboard, forecast, foreign, predictions, priors, reference,
    shortfall,
)
from src.api.schemas import HealthOut
from src.api.security import API_KEY_HEADER, require_api_key
from src.api.state import load_all
from src.config.settings import get_server_settings, settings

API_VERSION = "0.2"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("api")

# Fail closed: without API_KEY this raises before the app object exists, so
# uvicorn cannot import `src.api.main:app` and the server never starts.
get_server_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load every served artifact once, before the first request.

    Eager rather than lazy: a missing model should surface at startup, and the
    first caller should not pay a 1-2 second Prophet unpickle. Individual load
    failures are recorded on the artifact and surfaced as 500 model_not_loaded
    by the endpoints that need them, so one missing file cannot take the whole
    API down.
    """
    from src.api.routers.forecast import clear_forecast_cache

    from src.api.routers.shortfall import clear_shortfall_cache

    from src.api.routers.reference import clear_heatmap_memory
    from src.models.explainers import clear_explainers
    from src.models.prospectivity.explain import clear_bundle_cache
    from src.models.prospectivity.predict import clear_encoder_cache
    from src.models.registry import active_model, clear_pointer_cache

    clear_forecast_cache()
    clear_shortfall_cache()
    clear_heatmap_memory()
    clear_explainers()
    # The pointer and the bundles it names are re-read from disk, so a
    # promotion that happened while this process was down is picked up.
    clear_pointer_cache()
    clear_bundle_cache()
    clear_encoder_cache()
    app.state.artifacts = load_all()
    loaded = [name for name, a in app.state.artifacts.artifacts.items() if a.ok]
    failed = app.state.artifacts.degraded
    logger.info("startup: %d artifacts loaded%s", len(loaded),
                f", {len(failed)} failed: {', '.join(failed)}" if failed else "")
    logger.info("startup: %s required on every route", API_KEY_HEADER)
    serving = active_model()
    logger.info("startup: scoring with %s (%s)", serving.version, serving.source)
    app.state.registry_problems = _reconcile_registry()
    stop_warming = _start_heatmap_warming()
    yield
    stop_warming.set()
    app.state.artifacts = None


app = FastAPI(
    title="Manganese Prospectivity API",
    description=(
        "Manganese prospectivity and production forecasting. "
        "Phase 1 reference data, Phase 2 prospectivity scoring with geological masks, "
        "Phase 3 MOIL production forecasting and shortfall risk, "
        "Phase 4 dashboard endpoints."
    ),
    version=API_VERSION,
    lifespan=lifespan,
    dependencies=[Depends(require_api_key)],
)

#: Local frontend dev servers: CRA (3000), Vite (5173), and a plain static
#: server (8080). No production origin is configured - adding one is a
#: deliberate decision, not a default.
#: 3001 is the port the SIH frontend actually runs on (`npm run dev:sih`);
#: 3100 is the Playwright webServer. Without them the browser blocks every call
#: with a CORS error that reads like a network failure.
ALLOWED_ORIGINS = [
    f"http://{host}:{port}"
    for port in (3000, 3001, 3002, 3100, 5173, 8080)
    for host in ("localhost", "127.0.0.1")
]

#: Exactly what the frontend sends. No cookies or browser credentials are used,
#: so credentials stay off; the API key travels in its own header.
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Accept", "Content-Type", API_KEY_HEADER],
)

app.add_exception_handler(ApiError, api_error_handler)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    started = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = (time.perf_counter() - started) * 1000.0
    logger.info(
        "%s %s %s %.1fms",
        request.method,
        request.url.path,
        response.status_code,
        elapsed_ms,
    )
    response.headers["X-Elapsed-Ms"] = f"{elapsed_ms:.1f}"
    return response


def _start_heatmap_warming() -> threading.Event:
    """Warm the forecast, the point model and the demo viewports on a thread.

    A cold heatmap is ~38s per viewport, so warming three of them inline would
    block startup for roughly two minutes and make the API look hung. The
    thread is a daemon: warming is an optimisation, and it must never hold the
    process open or delay readiness. It then re-warms the viewports every
    MEMORY_TTL_SECONDS so they stay in memory; setting the returned event stops
    it at shutdown.
    """
    stop = threading.Event()

    def warm() -> None:
        from src.api.routers.reference import MEMORY_TTL_SECONDS, compute_heatmap
        from src.data.masks.registry import VALID_MASKS

        # Forecasts first: four horizons at ~1s each, and they are the
        # endpoint the dashboard hits on load. Prophet's MCMC posterior makes
        # a cold predict() ~950ms, over the 500ms target, so the first real
        # request should never be the one that pays it.
        try:
            from src.api.routers.forecast import VALID_HORIZONS, get_forecast

            class _Shim:
                app = None

            shim = _Shim()
            shim.app = app
            started = time.perf_counter()
            for horizon in VALID_HORIZONS:
                get_forecast(shim, horizon=horizon)
            logger.info("forecast warm %d horizons in %.1fs",
                        len(VALID_HORIZONS), time.perf_counter() - started)

            # SHAP makes a cold shortfall call ~6.6s; warm it too.
            from src.api.routers.shortfall import get_shortfall_risk

            started = time.perf_counter()
            get_shortfall_risk(shim)
            logger.info("shortfall warm in %.1fs", time.perf_counter() - started)
        except Exception as exc:  # noqa: BLE001 - warming must never break startup
            logger.warning("forecast warm failed: %s", exc)

        # The first /predict/point otherwise pays the torch and shap imports,
        # the autoencoder, the XGBoost bundle and the SHAP explainer: 26s
        # measured. Scored at the centre of the first warm viewport, which lies
        # inside the imagery footprint, and never written to the database.
        try:
            from src.models.prospectivity.predict import predict_point

            min_lon, min_lat, max_lon, max_lat = settings.HEATMAP_WARM_VIEWPORTS[0]["bbox"]
            started = time.perf_counter()
            predict_point((min_lat + max_lat) / 2, (min_lon + max_lon) / 2)
            logger.info("point model warm in %.1fs", time.perf_counter() - started)
        except Exception as exc:  # noqa: BLE001 - warming must never break startup
            logger.warning("point model warm failed: %s", exc)

        # Every mask, not just "none": the Explorer opens on mask=both, and a
        # masked surface is derived from the unmasked grid in well under a second.
        while not stop.is_set():
            for viewport in settings.HEATMAP_WARM_VIEWPORTS:
                name = viewport["name"]
                bbox = viewport["bbox"]
                started = time.perf_counter()
                for mask in VALID_MASKS:
                    try:
                        compute_heatmap(*bbox, grid_size=int(viewport["grid_size"]), mask=mask)
                    except Exception as exc:  # noqa: BLE001 - warming must never break startup
                        logger.warning("heatmap warm %s mask=%s failed: %s", name, mask, exc)
                logger.info("heatmap warm %s in %.1fs", name, time.perf_counter() - started)
            stop.wait(MEMORY_TTL_SECONDS)

    threading.Thread(target=warm, name="heatmap-warm", daemon=True).start()
    return stop


def _reconcile_registry() -> list[str]:
    """Check the database, the registry and the active pointer against each other."""
    from src.models.registry import reconcile

    recorded: list[tuple[str, str | None]] = []
    if settings.DATABASE_URL:
        try:
            from src.worker.jobs import TRAIN_TASK_NAME, published_artifacts

            recorded = [(a.version, a.sha256) for a in published_artifacts(TRAIN_TASK_NAME)]
        except SQLAlchemyError as exc:
            logger.warning("startup: could not read published artifacts: %s", exc)
    problems = reconcile(recorded)
    for problem in problems:
        logger.error("startup: model registry mismatch - %s", problem)
    return problems


@app.get("/", response_model=HealthOut, tags=["health"], summary="Health check")
def health(request: Request) -> HealthOut:
    from src.models.registry import active_model

    problems: list[str] = list(getattr(request.app.state, "registry_problems", []) or [])
    serving = active_model()
    return HealthOut(
        status="degraded" if problems else "ok",
        version=API_VERSION,
        model_version=serving.version,
        model_source=serving.source,
        degraded=problems,
    )


app.include_router(boreholes.router)
app.include_router(priors.router)
app.include_router(foreign.router)
app.include_router(predictions.router)
app.include_router(forecast.router)
app.include_router(reference.router)
app.include_router(shortfall.router)
app.include_router(dashboard.router)
