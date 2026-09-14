"""Engine and session factory for the Supabase/PostGIS database."""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.config.settings import settings

_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


def _normalise_url(url: str) -> str:
    """Force the psycopg (v3) driver, since that is what is installed."""
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg://", 1)
    return url


def get_engine() -> Engine:
    """Lazily-built process-wide engine.

    Built lazily so that importing this module never requires DATABASE_URL.

    On Supabase's transaction pooler (port 6543) a connection is handed to a
    different backend per transaction, so server-side prepared statements
    cannot be relied on; psycopg3 creates them by default after five reuses of
    a query. `prepare_threshold=None` disables that.
    """
    global _engine
    if _engine is None:
        url = _normalise_url(settings.require_database_url())
        connect_args: dict[str, object] = {}
        if ":6543/" in url:
            connect_args["prepare_threshold"] = None
        _engine = create_engine(
            url,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=5,
            future=True,
            connect_args=connect_args,
        )
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    global _session_factory
    if _session_factory is None:
        _session_factory = sessionmaker(
            bind=get_engine(), autoflush=False, autocommit=False, expire_on_commit=False
        )
    return _session_factory


def SessionLocal() -> Session:  # noqa: N802 - conventional factory name
    """Open a new Session. Caller is responsible for closing it."""
    return get_session_factory()()


def get_session() -> Iterator[Session]:
    """FastAPI dependency yielding a session and always closing it."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
